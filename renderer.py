import asyncio
import os
from jinja2 import Environment, FileSystemLoader

import optimizer
from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env = Environment(loader=FileSystemLoader(os.path.join(BASE_DIR, 'templates')))

# A4 dimensions in mm
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
PDF_MARGIN_MM = 15  # top / bottom margin used in PDF output
CONTENT_HEIGHT_MM = A4_HEIGHT_MM - 2 * PDF_MARGIN_MM  # 267mm usable


async def render_to_pdf(html_content, output_path):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html_content, wait_until='networkidle')
            await page.pdf(
                path=output_path,
                format='A4',
                print_background=True,
                margin={
                    'top': f'{PDF_MARGIN_MM}mm',
                    'right': f'{PDF_MARGIN_MM}mm',
                    'bottom': f'{PDF_MARGIN_MM}mm',
                    'left': f'{PDF_MARGIN_MM}mm',
                },
            )
            await browser.close()
        return True
    except Exception as e:
        print(f"PDF render error: {e}")
        return False


async def measure_page_fit(html_content):
    """
    Render HTML in headless browser and measure how well it fits one A4 page.

    Returns dict:
      fits        — True if content height ≤ content area + tolerance
      ratio       — scrollHeight / maxHeight (1.0 = perfect, >1 = overflow)
      scroll_px   — actual content height in px
      max_px      — available content area height in px
    """
    mm_to_px = 3.7795275591
    max_height_px = CONTENT_HEIGHT_MM * mm_to_px
    tolerance_px = 10  # ~2.6mm slop to avoid unnecessary iterations

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(html_content, wait_until='networkidle')

            result = await page.evaluate('''(maxHeight) => {
                const container = document.querySelector('.page') || document.body;
                const scrollH = container.scrollHeight;
                return {
                    scroll_px: scrollH,
                    max_px: maxHeight,
                    ratio: scrollH / maxHeight,
                    fits: scrollH <= maxHeight + 10
                };
            }''', max_height_px)

            await browser.close()
            return result
    except Exception as e:
        print(f"[measure_page_fit] error: {e}")
        return {"fits": True, "ratio": 1.0, "scroll_px": 0, "max_px": max_height_px}


async def measure_page_fit_with_retry(html_content, retries=2):
    results = []
    for _ in range(retries):
        r = await measure_page_fit(html_content)
        results.append(r["ratio"])
    avg_ratio = sum(results) / len(results)
    first = results[0]
    return {
        "fits": avg_ratio <= 1.02,  # allow 2% average overflow
        "ratio": avg_ratio,
        "scroll_px": first.get("scroll_px", 0),
        "max_px": first.get("max_px", 0),
    }


def preview_html(profile_data, language='en', optimized_content=None):
    template_name = 'resume_en.html' if language == 'en' else 'resume_cn.html'
    template = env.get_template(template_name)
    html = template.render(profile=profile_data, optimized_content=optimized_content)

    css_path = os.path.join(BASE_DIR, 'css', 'resume.css')
    if os.path.exists(css_path):
        with open(css_path) as f:
            css = f.read()
        html = html.replace(
            '<link rel="stylesheet" href="../css/resume.css">',
            f'<style>{css}</style>',
        )

    return html


def generate_resume(profile, job_requirements, language='en', output_dir='output'):
    os.makedirs(output_dir, exist_ok=True)
    optimized = optimizer.optimize_for_job(profile, job_requirements, language)
    html = preview_html(optimized, language)
    safe_lang = 'en' if language == 'en' else 'cn'
    name_slug = (
        profile.get('personal_info', {})
        .get('name_en', 'resume')
        .replace(' ', '_')
        .lower()
    )
    output_path = os.path.join(output_dir, f'{name_slug}_{safe_lang}.pdf')
    asyncio.run(render_to_pdf(html, output_path))
    return os.path.abspath(output_path)
