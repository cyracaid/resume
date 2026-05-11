import asyncio
import os
import streamlit as st
import yaml
from pathlib import Path

import scraper
import optimizer
import renderer
import layout_controller

BASE_DIR = Path(__file__).parent
PROFILE_PATH = BASE_DIR / "profile.yaml"


def load_profile():
    if not PROFILE_PATH.exists():
        st.error(f"profile.yaml not found at {PROFILE_PATH}")
        return {}
    with open(PROFILE_PATH, "r") as f:
        return yaml.safe_load(f)


def render_profile():
    profile = st.session_state.get("profile", {})
    if not profile:
        st.warning("No profile data loaded.")
        return

    pi = profile.get("personal_info", {})
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader(pi.get("name_en", "Unknown"))
        st.caption(pi.get("location_preference", ""))
    with col2:
        st.markdown(f"**Email:** {pi.get('email', '—')}")
        st.markdown(f"**Phone:** {pi.get('phone_us', '—')}")
        st.markdown(f"**Location:** {pi.get('location_preference', '—')}")
        links = []
        if pi.get("linkedin"):
            links.append(f"[LinkedIn]({pi['linkedin']})")
        if links:
            st.markdown(" | ".join(links))

    summary_key = st.session_state.get("summary_lang", "summary_en")
    if pi.get(summary_key):
        st.markdown("---")
        st.markdown("### Professional Summary")
        st.markdown(pi[summary_key])

    skills = profile.get("skills", {})
    if skills:
        st.markdown("---")
        st.markdown("### Skills")
        for category, items in skills.items():
            st.markdown(f"**{category.capitalize()}:** {', '.join(items)}")

    exp = profile.get("experience", {})
    research = exp.get("research", [])
    if research:
        st.markdown("---")
        st.markdown("### Research Experience")
        for entry in research:
            with st.container(border=True):
                st.markdown(f"**{entry.get('role')}** @ {entry.get('institution')}")
                meta = entry.get("period", "")
                if entry.get("location"):
                    meta += f" | {entry['location']}"
                if entry.get("mentor"):
                    meta += f" | Mentor: {entry['mentor']}"
                st.caption(meta)
                for h in entry.get("highlights_en", []):
                    st.markdown(f"- {h}")

    teaching = exp.get("teaching", [])
    if teaching:
        st.markdown("---")
        st.markdown("### Teaching Experience")
        for entry in teaching:
            with st.container(border=True):
                st.markdown(f"**{entry.get('role')}** @ {entry.get('institution')}")
                st.caption(f"{entry.get('period')} | {entry.get('location')}")

    clinical = exp.get("clinical", [])
    if clinical:
        st.markdown("---")
        st.markdown("### Clinical Experience")
        for entry in clinical:
            with st.container(border=True):
                st.markdown(f"**{entry.get('role')}** @ {entry.get('institution')}")
                st.caption(f"{entry.get('period')} | {entry.get('location')}")

    education = profile.get("education", [])
    if education:
        st.markdown("---")
        st.markdown("### Education")
        for edu in education:
            majors_str = f" ({', '.join(edu.get('majors', []))})" if edu.get("majors") else ""
            st.markdown(f"**{edu.get('degree')}**{majors_str} — {edu.get('institution')}")
            meta = edu.get("period", "")
            if edu.get("location"):
                meta += f" | {edu['location']}"
            if edu.get("gpa"):
                meta += f" | GPA: {edu['gpa']}"
            st.caption(meta)

    projects = profile.get("projects", [])
    if projects:
        st.markdown("---")
        st.markdown("### Projects")
        for proj in projects:
            with st.container(border=True):
                st.markdown(f"**{proj.get('title')}** — {proj.get('institution')}")
                st.markdown(proj.get("description_en", ""))

    publications = profile.get("publications", [])
    if publications:
        st.markdown("---")
        st.markdown("### Publications")
        for pub in publications:
            st.markdown(
                f"{pub.get('authors', '')} ({pub.get('year', '')}). "
                f"\"{pub.get('title', '')}\" *{pub.get('journal', '')}*"
            )

    languages = profile.get("languages", [])
    if languages:
        st.markdown("---")
        st.markdown("### Languages")
        for lang in languages:
            details = f" ({lang.get('details', '')})" if lang.get("details") else ""
            st.markdown(f"{lang.get('language')} — {lang.get('proficiency')}{details}")

    honors = profile.get("honors", [])
    if honors:
        st.markdown("---")
        st.markdown("### Honors & Awards")
        for h in honors:
            parts = [h.get("name", "")]
            if h.get("institution"):
                parts.append(h["institution"])
            if h.get("period"):
                parts.append(f"({h['period']})")
            elif h.get("year"):
                parts.append(f"({h['year']})")
            st.markdown(f"- {' — '.join(parts)}")

    certs = profile.get("certifications", [])
    if certs:
        st.markdown("---")
        st.markdown("### Certifications")
        for c in certs:
            parts = [c.get("name", "")]
            if c.get("issuer"):
                parts.append(c["issuer"])
            st.markdown(f"- {' — '.join(parts)}")

    posters = profile.get("conference_posters", [])
    if posters:
        st.markdown("---")
        st.markdown("### Conference Posters")
        for p in posters:
            st.markdown(f"- {p.get('title')} — {p.get('conference')} ({p.get('year')})")


def render_job_target():
    st.text_input("Position Title", key="position_title")
    jd_url = st.text_area(
        "Job Description URL", key="jd_url", placeholder="https://..."
    )
    jd_text = st.text_area(
        "Or paste Job Description text",
        key="jd_text",
        height=200,
        placeholder="Paste the full job description here...",
    )

    if st.button("Analyze Job Description"):
        pos = st.session_state.get("position_title", "")
        if not pos:
            st.warning("Please enter a position title.")
            return
        if not jd_url and not jd_text:
            st.warning("Please provide a job description URL or paste the text.")
            return

        with st.spinner("Analyzing job description..."):
            result = scraper.analyze_job_target(pos, jd_url, jd_text)

        if "error" in result:
            st.error(result["error"])
            return

        st.session_state["job_requirements"] = result
        st.success("Job description analyzed!")

    jr = st.session_state.get("job_requirements")
    if jr:
        st.markdown("---")
        st.markdown("### Analysis Results")
        st.markdown(f"**Position:** {jr.get('position_title', '')}")
        if jr.get("required_skills"):
            st.markdown(f"**Required Skills:** {', '.join(jr['required_skills'])}")
        if jr.get("nice_to_have"):
            st.markdown(f"**Nice to Have:** {', '.join(jr['nice_to_have'])}")
        if jr.get("responsibilities"):
            with st.expander("Responsibilities"):
                for r in jr["responsibilities"]:
                    st.markdown(f"- {r}")
        if jr.get("education_requirements"):
            st.markdown(f"**Education:** {jr['education_requirements']}")
        if jr.get("keywords"):
            with st.expander(f"Keywords ({len(jr['keywords'])})"):
                st.write(", ".join(jr["keywords"][:50]))


def _do_layout_regenerate(language):
    profile = st.session_state.get("profile", {})
    jr = st.session_state.get("job_requirements")
    if not jr:
        st.warning("Analyze a job description first (Job Target tab).")
        return

    lang_key = "en" if language == "en" else "cn"
    with st.spinner(f"Generating layout-optimized resume ({lang_key})..."):
        result = layout_controller.generate_layout_controlled(
            profile, jr, language=language, max_iterations=5
        )
        st.session_state[f"layout_result_{lang_key}"] = result
        st.session_state[f"optimized_content_{lang_key}"] = result["content"]

        html = renderer.preview_html(
            profile, language=language,
            optimized_content=result["content"]
        )
        st.session_state[f"html_preview_{lang_key}"] = html

    status = "fits" if result["fits"] else "near-miss"
    st.success(
        f"Resume generated ({lang_key}) — "
        f"level={result['level']}, "
        f"iterations={result['iterations']}, "
        f"fill={result['ratio']:.1%}, "
        f"status={status}"
    )


def _make_pdf(language):
    lang_key = "en" if language == "en" else "cn"
    profile = st.session_state.get("profile", {})
    optimized_content = st.session_state.get(f"optimized_content_{lang_key}")

    safe_lang = lang_key
    name_slug = (
        profile.get("personal_info", {})
        .get("name_en", "resume")
        .replace(" ", "_")
        .lower()
    )
    output_dir = BASE_DIR / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{name_slug}_{safe_lang}.pdf"

    html = renderer.preview_html(profile, language=language,
                                 optimized_content=optimized_content)
    asyncio.run(renderer.render_to_pdf(html, str(output_path)))
    return str(output_path)


def render_preview():
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("English Resume")
        if st.button("Regenerate (EN) - Layout Controlled", key="regenerate_en"):
            _do_layout_regenerate("en")
        lr_en = st.session_state.get("layout_result_en")
        if lr_en:
            st.caption(
                f"Level {lr_en['level']} | {lr_en['iterations']} iters | "
                f"Fill {lr_en['ratio']:.1%} | "
                f"{'FITS' if lr_en['fits'] else 'NEAR-MISS'}"
            )
        if st.session_state.get("html_preview_en"):
            st.components.v1.html(
                st.session_state["html_preview_en"], height=500, scrolling=True
            )
            st.button("Approve (EN)", key="approve_en")
        else:
            st.info("Click 'Regenerate (EN)' to optimize and preview.")

    with col2:
        st.subheader("Chinese Resume")
        if st.button("Regenerate (CN) - Layout Controlled", key="regenerate_cn"):
            _do_layout_regenerate("cn")
        lr_cn = st.session_state.get("layout_result_cn")
        if lr_cn:
            st.caption(
                f"Level {lr_cn['level']} | {lr_cn['iterations']} iters | "
                f"Fill {lr_cn['ratio']:.1%} | "
                f"{'FITS' if lr_cn['fits'] else 'NEAR-MISS'}"
            )
        if st.session_state.get("html_preview_cn"):
            st.components.v1.html(
                st.session_state["html_preview_cn"], height=500, scrolling=True
            )
            st.button("Approve (CN)", key="approve_cn")
        else:
            st.info("Click 'Regenerate (CN)' to optimize and preview.")


def render_export():
    st.markdown("### Export Options")
    st.info(
        "Optimize your resume in the **Preview** tab first, "
        "then generate PDFs here. Quick Export skips optimization."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("English PDF")
        if st.button("Generate PDF (EN)", key="gen_pdf_en"):
            with st.spinner("Generating PDF..."):
                path = _make_pdf("en")
            st.success("PDF generated!")
            with open(path, "rb") as f:
                st.download_button(
                    "Download PDF (EN)",
                    f,
                    file_name=os.path.basename(path),
                    mime="application/pdf",
                )

    with col2:
        st.subheader("Chinese PDF")
        if st.button("Generate PDF (CN)", key="gen_pdf_cn"):
            with st.spinner("Generating PDF..."):
                path = _make_pdf("cn")
            st.success("PDF generated!")
            with open(path, "rb") as f:
                st.download_button(
                    "Download PDF (CN)",
                    f,
                    file_name=os.path.basename(path),
                    mime="application/pdf",
                )

    st.markdown("---")
    st.markdown("### Quick Export (Original Profile, No Layout Optimization)")

    qc1, qc2 = st.columns(2)
    with qc1:
        if st.button("Generate PDF (Original EN)", key="gen_pdf_orig_en"):
            profile = st.session_state.get("profile", {})
            with st.spinner("Generating PDF..."):
                path = renderer.generate_resume(profile, {}, language="en")
            st.success("PDF generated!")
            with open(path, "rb") as f:
                st.download_button(
                    "Download (EN Orig)",
                    f,
                    file_name=os.path.basename(path),
                    mime="application/pdf",
                    key="dl_orig_en",
                )
    with qc2:
        if st.button("Generate PDF (Original CN)", key="gen_pdf_orig_cn"):
            profile = st.session_state.get("profile", {})
            with st.spinner("Generating PDF..."):
                path = renderer.generate_resume(profile, {}, language="cn")
            st.success("PDF generated!")
            with open(path, "rb") as f:
                st.download_button(
                    "Download (CN Orig)",
                    f,
                    file_name=os.path.basename(path),
                    mime="application/pdf",
                    key="dl_orig_cn",
                )


PAGES = {
    "Profile": render_profile,
    "Job Target": render_job_target,
    "Preview": render_preview,
    "Export": render_export,
}


def main():
    st.set_page_config(
        page_title="Resume Beautifier Agent",
        page_icon="",
        layout="wide",
    )

    if "profile" not in st.session_state:
        st.session_state["profile"] = load_profile()
    if "summary_lang" not in st.session_state:
        st.session_state["summary_lang"] = "summary_en"

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", list(PAGES.keys()), key="nav_page")

    st.title(f"{page}")
    st.sidebar.markdown("---")
    st.sidebar.caption("Resume Beautifier Agent v0.2 — Layout Controlled")

    PAGES[page]()


if __name__ == "__main__":
    main()
