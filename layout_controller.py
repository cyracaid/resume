"""
Layout-constrained resume generation.

Iterative control loop:
  1. Generate content at a given compression level
  2. Render to HTML
  3. Measure rendered page height via Playwright
  4. If overflow/underflow, adjust compression level and loop
  5. Return content that fits exactly one page
"""

import asyncio

import optimizer
import renderer

# A4 content area (297mm - 15mm top - 15mm bottom)
CONTENT_HEIGHT_MM = 267.0


def generate_layout_controlled(profile, job_requirements=None,
                                language="en", max_iterations=5):
    """
    Generate resume content that fits exactly one A4 page.

    Parameters
    ----------
    profile : dict
        Full profile data from profile.yaml.
    job_requirements : dict or None
        Output of scraper.analyze_job_target().
    language : str
        "en" or "cn".
    max_iterations : int
        Maximum number of generate-measure-adjust cycles.

    Returns
    -------
    dict with keys:
        content     — structured optimized_content dict
        level       — final compression level used
        iterations  — number of iterations taken
        ratio       — final content-height / available-height ratio
        fits        — True if the result fits within one page
    """
    level = 0
    best = None

    for iteration in range(max_iterations):
        content = optimizer.generate_all_content(
            profile, job_requirements, language, level
        )

        html = renderer.preview_html(profile, language,
                                     optimized_content=content)

        result = asyncio.run(renderer.measure_page_fit_with_retry(html))
        ratio = result["ratio"]
        fits = result["fits"]

        best = (level, content, ratio, fits)

        if fits:
            return _result(content, level, iteration + 1, ratio, True)

        if ratio > 1.0:
            if level >= 2:
                return _result(content, level, iteration + 1, ratio, False)
            level += 1
        else:
            if level <= -2:
                return _result(content, level, iteration + 1, ratio, True)
            level -= 1

    _, content, ratio, fits = best
    return _result(content, level, max_iterations, ratio, fits)


def _result(content, level, iterations, ratio, fits):
    return {
        "content": content,
        "level": level,
        "iterations": iterations,
        "ratio": ratio,
        "fits": fits,
    }
