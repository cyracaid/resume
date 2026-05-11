import re
import urllib.request
import urllib.error
import socket
from html.parser import HTMLParser


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

    def get_text(self):
        return " ".join(self._text)


_SECTION_PATTERNS = [
    re.compile(r"(?:requirements|qualifications|what you[^.]*need|you have|you are|about you|we.re looking for)", re.IGNORECASE),
    re.compile(r"(?:nice to have|bonus points|preferred|plus|desired|good to have)", re.IGNORECASE),
    re.compile(r"(?:responsibilities|what you[^.]*do|key duties|role overview|about the role)", re.IGNORECASE),
]

_SKILL_SEPARATOR = re.compile(r"[,;•·∙◦➢➤▪▸→•\n|]|(?:\s+(?:and|or)\s+)")
_BULLET_LINE = re.compile(r"^\s*[•·∙◦➢➤▪▸→\-*\d+.)]\s*")
_WHITESPACE = re.compile(r"\s+")

COMMON_SKILLS = {
    "python", "java", "javascript", "typescript", "go", "golang", "rust",
    "c++", "c#", "csharp", "ruby", "swift", "kotlin", "scala", "php",
    "react", "angular", "vue", "vue.js", "svelte", "node.js", "nodejs",
    "django", "flask", "fastapi", "spring", "rails", "express",
    "pytorch", "tensorflow", "keras", "jax", "scikit-learn", "sklearn",
    "pandas", "numpy", "spacy", "transformers", "hugging face", "langchain",
    "kubernetes", "k8s", "docker", "aws", "gcp", "azure", "terraform",
    "ansible", "jenkins", "ci/cd", "gitlab", "github actions",
    "sql", "postgresql", "postgres", "mysql", "mongodb", "redis",
    "elasticsearch", "kafka", "spark", "hadoop", "airflow",
    "graphql", "rest", "grpc", "api",
    "machine learning", "ml", "deep learning", "nlp", "computer vision",
    "llm", "rag", "fine-tuning", "prompt engineering",
    "git", "linux", "bash", "shell", "agile", "scrum",
}

_EDUCATION_PATTERNS = [
    re.compile(r"(?:bachelor|master|phd|doctorate|b\.s\.|m\.s\.|b\.a\.|m\.a\.)[^.]*", re.IGNORECASE),
    re.compile(r"(?:degree|education)[^.]*(?:required|preferred|must have)", re.IGNORECASE),
    re.compile(r"(?:bs|ms|phd)\s+(?:in|degree)", re.IGNORECASE),
]


def _fetch_url(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            encoding = resp.headers.get_content_charset() or "utf-8"
            html = raw.decode(encoding, errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout, OSError) as e:
        raise RuntimeError(f"Failed to fetch URL: {e}")

    extractor = _HTMLTextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        pass
    return extractor.get_text()


def _extract_section(text, patterns):
    for pat in patterns:
        m = pat.search(text)
        if m:
            start = m.end()
            rest = text[start:]
            lines = []
            for line in rest.split("\n"):
                stripped = line.strip()
                if not stripped:
                    if len(lines) > 2:
                        break
                    continue
                lines.append(stripped)
            return " ".join(lines[:20])
    return ""


def _extract_skills(text, section_name=""):
    found = set()
    normalized = _WHITESPACE.sub(" ", text).lower()
    for skill in COMMON_SKILLS:
        if skill in normalized:
            found.add(skill)
    return sorted(found)


def _extract_education(text):
    for pat in _EDUCATION_PATTERNS:
        m = pat.search(text)
        if m:
            return _WHITESPACE.sub(" ", m.group(0)).strip()
    return None


def _extract_keywords(text):
    words = _WHITESPACE.sub(" ", text).lower().split()
    stopwords = {
        "the", "a", "an", "and", "or", "of", "in", "to", "for", "with",
        "on", "at", "by", "is", "are", "was", "were", "be", "been",
        "this", "that", "it", "we", "you", "our", "your", "their",
    }
    keywords = set()
    for w in words:
        w_clean = w.strip(",.!?;:()[]{}'\"")
        if len(w_clean) > 2 and w_clean not in stopwords:
            keywords.add(w_clean)
    return sorted(keywords)


def analyze_job_target(position_title, jd_url=None, jd_text=None):
    if not jd_url and not jd_text:
        return {"error": "Provide either jd_url or jd_text."}

    if jd_url:
        try:
            jd_text = _fetch_url(jd_url)
        except RuntimeError:
            return {
                "error": "Could not fetch job description from URL. "
                         "Please paste the job description text directly "
                         "using jd_text= instead."
            }
    else:
        jd_text = jd_text or ""

    req_section = _extract_section(jd_text, _SECTION_PATTERNS[:1])
    nice_section = _extract_section(jd_text, _SECTION_PATTERNS[1:2])
    resp_section = _extract_section(jd_text, _SECTION_PATTERNS[2:])

    return {
        "company": None,
        "position_title": position_title,
        "required_skills": _extract_skills(req_section, "required"),
        "nice_to_have": _extract_skills(nice_section, "nice"),
        "responsibilities": (
            [line.strip() for line in resp_section.split(". ") if len(line.strip()) > 10]
            if resp_section
            else []
        ),
        "keywords": _extract_keywords(jd_text),
        "education_requirements": _extract_education(jd_text),
    }
