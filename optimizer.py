"""Resume content optimizer with layout-constrained LLM generation."""

import json
import re

import ollama

MODEL = "qwen2.5:7b"

# Compression profiles mapping level → content density targets
COMPRESSION_PROFILES = {
    -2: {
        "label": "maximum expansion",
        "bullets_per_experience": (4, 6),
        "bullets_per_education": (2, 3),
        "summary_lines": (2, 3),
        "bullet_max_chars": 180,
        "verbosity": "detailed, with technical specificity and quantified outcomes",
    },
    -1: {
        "label": "slight expansion",
        "bullets_per_experience": (3, 5),
        "bullets_per_education": (1, 2),
        "summary_lines": (2, 3),
        "bullet_max_chars": 150,
        "verbosity": "moderately detailed",
    },
    0: {
        "label": "normal",
        "bullets_per_experience": (3, 4),
        "bullets_per_education": (1, 2),
        "summary_lines": (1, 2),
        "bullet_max_chars": 130,
        "verbosity": "concise but specific",
    },
    1: {
        "label": "compress",
        "bullets_per_experience": (2, 3),
        "bullets_per_education": (0, 1),
        "summary_lines": (1, 2),
        "bullet_max_chars": 100,
        "verbosity": "compact, every word counts",
    },
    2: {
        "label": "aggressive compression",
        "bullets_per_experience": (1, 2),
        "bullets_per_education": (0, 1),
        "summary_lines": (1, 1),
        "bullet_max_chars": 80,
        "verbosity": "ultra-compact, strongest bullets only",
    },
}


def test_ollama_connection():
    try:
        ollama.chat(model=MODEL, messages=[{"role": "user", "content": "Hi"}])
        return True, "Connection successful"
    except Exception as e:
        return False, str(e)


def _call_llm(system_prompt, user_prompt, temperature=0.3):
    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        options={"temperature": temperature},
    )
    return response["message"]["content"].strip()


def _parse_json_from_llm(text):
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    # Find outermost braces
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        text = text[brace_start : brace_end + 1]
    return json.loads(text)


def _summarise_profile(profile):
    pi = profile.get("personal_info", {})
    lines = [f"Name: {pi.get('name_en', '')} / {pi.get('name_cn', '')}"]
    lines.append("\n--- EDUCATION ---")
    for edu in profile.get("education", []):
        majors = " & ".join(edu.get("majors", []))
        lines.append(
            f"- {edu.get('degree')} ({majors}) @ {edu.get('institution')}, "
            f"{edu.get('location')} ({edu.get('period')}) GPA: {edu.get('gpa', 'N/A')}"
        )
    lines.append("\n--- RESEARCH EXPERIENCE ---")
    for exp in profile.get("experience", {}).get("research", []):
        lines.append(f"- {exp.get('role')} @ {exp.get('institution')} ({exp.get('period')})")
        for h in exp.get("highlights_en", []) or exp.get("highlights_cn", []):
            lines.append(f"  • {h}")
    for cat in ("teaching", "clinical"):
        entries = profile.get("experience", {}).get(cat, [])
        if entries:
            lines.append(f"\n--- {cat.upper()} ---")
            for exp in entries:
                lines.append(f"- {exp.get('role')} @ {exp.get('institution')} ({exp.get('period')})")
    lines.append("\n--- PROJECTS ---")
    for proj in profile.get("projects", []):
        lines.append(f"- {proj.get('title')} @ {proj.get('institution')}")
    lines.append("\n--- SKILLS ---")
    for cat, items in profile.get("skills", {}).items():
        lines.append(f"  {cat}: {', '.join(items)}")
    pubs = profile.get("publications", [])
    if pubs:
        lines.append("\n--- PUBLICATIONS ---")
        for pub in pubs:
            lines.append(f"  {pub.get('authors', '')} ({pub.get('year', '')}) {pub.get('title', '')} — {pub.get('journal', '')}")
    return "\n".join(lines)


def _build_layout_prompt(profile_text, job_req, language, level):
    profile = COMPRESSION_PROFILES.get(level, COMPRESSION_PROFILES[0])
    bullet_range = profile["bullets_per_experience"]
    edu_bullet_range = profile["bullets_per_education"]
    summary_lines = profile["summary_lines"]
    max_chars = profile["bullet_max_chars"]
    verbosity = profile["verbosity"]

    jd_info = ""
    if job_req:
        pos = job_req.get("position_title", "")
        skills = ", ".join(job_req.get("required_skills", []))
        resp = "; ".join(job_req.get("responsibilities", []))
        if pos or skills or resp:
            jd_info = f"""
TARGET JOB: {pos}
REQUIRED SKILLS: {skills}
RESPONSIBILITIES: {resp}
"""

    lang_notes = {
        "en": {
            "lang": "English",
            "style": "Use concise, technically credible wording. Avoid unnecessary articles. Prefer strong verbs. No buzzwords or fluff.",
            "summary_label": "Professional Summary",
            "edu_label": "Education Highlights",
            "exp_label": "Research Experience",
        },
        "cn": {
            "lang": "Chinese",
            "style": "使用简洁专业的中文。避免翻译腔。保持技术精确性。考虑中文字符的视觉密度更大，bullet数量应比英文少20%。",
            "summary_label": "个人简介",
            "edu_label": "教育背景要点",
            "exp_label": "研究经历",
        },
    }[language]

    system_prompt = (
        "You are a resume layout optimizer. You generate resume content that fits "
        "strictly within a one-page A4 layout. You must return ONLY valid JSON "
        "with no markdown fences, no extra commentary.\n\n"
        f"Compression mode: {profile['label']}\n"
        f"Verbosity: {verbosity}\n"
        f"Max chars per bullet: {max_chars}\n"
    )

    user_prompt = f"""Generate a complete one-page resume in {lang_notes['lang']} based on the profile below.

{jd_info}
LAYOUT CONSTRAINTS (CRITICAL — must follow exactly):
- Compression level: {profile['label']}
- Professional summary: {summary_lines[0]}-{summary_lines[1]} sentences
- Each research experience entry: {bullet_range[0]}-{bullet_range[1]} bullet points
- Each education entry: {edu_bullet_range[0]}-{edu_bullet_range[1]} bullet points
- Maximum bullet length: {max_chars} characters each
- Language style: {lang_notes['style']}

PRIORITY RULES:
- Keep ALL facts accurate — do NOT hallucinate, change dates, or alter institutions/titles
- Quantify impact where possible
- Prioritise strongest, most recent experiences
- If content must be cut, remove weaker/older details first
- preserve quantified outcomes over descriptive language

PROFILE DATA:
{profile_text}

Return ONLY a JSON object with this exact structure:
{{
  "summary": "string",
  "education": [
    ["bullet1", "bullet2"]
  ],
  "experience": {{
    "research": [
      {{"highlights": ["bullet1", "bullet2"]}}
    ]
  }}
}}

The education array order and research array order must match the profile data order."""

    return system_prompt, user_prompt


# ── Public API ───────────────────────────────────────────────────────────────

def generate_all_content(profile, job_requirements=None, language="en", level=0):
    """
    Generate complete resume content (summary + all bullets) at a given
    compression level.

    Parameters
    ----------
    profile : dict
        Full profile data from profile.yaml.
    job_requirements : dict or None
        Output of scraper.analyze_job_target().
    language : str
        "en" or "cn".
    level : int
        Compression level: -2 (expand) to +2 (compress). 0 = normal.

    Returns
    -------
    dict
        Structured content matching template's `optimized_content` interface.
    """
    profile_text = _summarise_profile(profile)
    system_prompt, user_prompt = _build_layout_prompt(
        profile_text, job_requirements or {}, language, level
    )

    raw = _call_llm(system_prompt, user_prompt, temperature=0.2)
    try:
        content = _parse_json_from_llm(raw)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[optimizer] JSON parse failed at level {level}: {e}")
        print(f"[optimizer] Raw output:\n{raw[:500]}")
        # Fallback: return empty structure so template renders original data
        return _empty_content(profile, language)

    # Validate / repair structure
    content = _ensure_structure(content, profile, language)
    return content


def _empty_content(profile, language):
    n_edu = len(profile.get("education", []))
    n_research = len(profile.get("experience", {}).get("research", []))
    return {
        "summary": None,
        "education": [[] for _ in range(n_edu)],
        "experience": {
            "research": [{"highlights": []} for _ in range(n_research)],
        },
    }


def _ensure_structure(content, profile, language):
    if not isinstance(content, dict):
        return _empty_content(profile, language)

    n_edu = len(profile.get("education", []))
    n_research = len(profile.get("experience", {}).get("research", []))

    if "summary" not in content:
        content["summary"] = None

    # Education
    edu = content.get("education", [])
    while len(edu) < n_edu:
        edu.append([])
    content["education"] = edu[:n_edu]

    # Experience
    exp = content.get("experience", {})
    if not isinstance(exp, dict):
        exp = {}
    research = exp.get("research", [])
    while len(research) < n_research:
        research.append({"highlights": []})
    for i, r in enumerate(research[:n_research]):
        if not isinstance(r, dict):
            research[i] = {"highlights": []}
        elif "highlights" not in r:
            r["highlights"] = []
    content["experience"] = {"research": research[:n_research]}

    return content


# Legacy interface — used by app.py quick-export path
def optimize_for_job(profile, job_requirements, language="en", dry_run=False):
    if dry_run:
        return profile

    profile = profile.copy()
    profile["experience"] = profile.get("experience", {}).copy()
    research = profile["experience"].get("research", [])

    key = "highlights_en" if language == "en" else "highlights_cn"

    entries_with_bullets = [
        (i, entry) for i, entry in enumerate(research) if entry.get(key)
    ]

    for i, entry in entries_with_bullets:
        original = entry[key]
        try:
            rewritten = _optimize_bullets(original, job_requirements, language)
            profile["experience"]["research"][i][key] = rewritten if rewritten else original
        except Exception:
            profile["experience"]["research"][i][key] = original

    return profile


def _build_prompt(bullets, job_req, language):
    position_title = job_req.get("position_title", "Unknown Position")
    required_skills = ", ".join(job_req.get("required_skills", []))
    responsibilities = "; ".join(job_req.get("responsibilities", []))

    bullets_text = "\n".join(f"- {b}" for b in bullets)

    prompt = f"""You are a resume optimization assistant. Rewrite the following resume bullet points to better match the target job description. Keep ALL facts accurate — do NOT hallucinate experience, change dates, or alter institutions/titles. Use active voice and quantify impacts where possible.

TARGET JOB: {position_title}
REQUIRED SKILLS: {required_skills}
RESPONSIBILITIES: {responsibilities}

ORIGINAL BULLET POINTS:
{bullets_text}

Return ONLY the rewritten bullet points, one per line, no numbering."""

    return prompt


def _optimize_bullets(bullets, job_req, language):
    prompt = _build_prompt(bullets, job_req, language)
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response["message"]["content"].strip()
    rewritten = [
        line.strip().lstrip("- ").strip()
        for line in raw.split("\n")
        if line.strip()
    ]
    return rewritten
