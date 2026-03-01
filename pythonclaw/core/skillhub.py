"""
SkillHub marketplace client for PythonClaw.

Integrates with https://www.skillhub.club/ API to search, browse,
and install community skills directly into the local skill directory.
"""

from __future__ import annotations

import json
import logging
import os
import re
import ssl
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

API_BASE = "https://www.skillhub.club/api/v1"
SKILL_PAGE_BASE = "https://www.skillhub.club/skills"


def _get_ssl_ctx() -> ssl.SSLContext:
    """Build an SSL context; use unverified fallback for macOS cert issues."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _api_key() -> str:
    """Read SkillHub API key from config or environment."""
    from .. import config
    return config.get_str("skillhub", "apiKey", env="SKILLHUB_API_KEY")


def _api_request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    params: dict | None = None,
) -> dict:
    """Make an authenticated request to the SkillHub API."""
    api_key = _api_key()

    url = f"{API_BASE}{path}"
    if params:
        qs = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items() if v is not None)
        if qs:
            url = f"{url}?{qs}"

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=15, context=_get_ssl_ctx()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        logger.warning("SkillHub API error %s: %s", exc.code, err_body)
        raise RuntimeError(f"SkillHub API error ({exc.code}): {err_body}") from exc
    except Exception as exc:
        raise RuntimeError(f"SkillHub request failed: {exc}") from exc


def search(query: str, *, limit: int = 10, category: str | None = None) -> list[dict]:
    """Search SkillHub for skills matching a query."""
    body: dict[str, Any] = {"query": query, "limit": limit, "method": "hybrid"}
    if category:
        body["category"] = category
    result = _api_request("POST", "/skills/search", body=body)
    return result.get("results", result.get("skills", []))


def browse(*, limit: int = 20, sort: str = "score", category: str | None = None) -> list[dict]:
    """Browse the SkillHub catalog."""
    params: dict[str, Any] = {"limit": limit, "sort": sort}
    if category:
        params["category"] = category
    result = _api_request("GET", "/skills/catalog", params=params)
    return result.get("results", result.get("skills", []))


def get_skill_detail(skill_id: str) -> dict | None:
    """Fetch full detail for a skill, including SKILL.md content.

    Tries the API first, falls back to scraping the skill page.
    """
    try:
        result = _api_request("GET", f"/skills/{skill_id}")
        skill = result.get("skill", result)
        return {
            "id": skill.get("slug", skill.get("id", skill_id)),
            "name": skill.get("name", ""),
            "description": skill.get("description", ""),
            "skill_md": skill.get("skill_md_raw", skill.get("skill_md", "")),
            "category": skill.get("category", ""),
            "author": skill.get("author", ""),
            "score": skill.get("composite_score", skill.get("simple_score", "")),
            "stars": skill.get("github_stars", ""),
            "source_url": skill.get("repo_url", f"{SKILL_PAGE_BASE}/{skill_id}"),
        }
    except Exception:
        pass

    return _scrape_skill_page(skill_id)


def _scrape_skill_page(skill_id: str) -> dict | None:
    """Fallback: scrape the skill page for SKILL.md content."""
    url = f"{SKILL_PAGE_BASE}/{skill_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "PythonClaw/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15, context=_get_ssl_ctx()) as resp:
            html = resp.read().decode("utf-8")
    except Exception as exc:
        logger.warning("Failed to fetch skill page %s: %s", url, exc)
        return None

    skill_md = _extract_skill_md(html)
    if not skill_md:
        return None

    name_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    name = name_match.group(1).strip() if name_match else skill_id.split("-")[-1]
    name = re.sub(r"<[^>]+>", "", name).strip()

    desc = ""
    fm_match = re.search(r"^description:\s*>?\s*(.+?)$", skill_md, re.MULTILINE)
    if fm_match:
        desc = fm_match.group(1).strip()

    return {
        "id": skill_id,
        "name": name,
        "description": desc,
        "skill_md": skill_md,
        "source_url": url,
    }


def _extract_skill_md(html: str) -> str | None:
    """Extract SKILL.md content from a skill page HTML."""
    # SkillHub renders skill content inside a prose-skill container.
    # The frontmatter appears as <hr/> then <h2>name: ... description: ...
    # followed by the instruction body.

    m = re.search(
        r'class="[^"]*prose-skill[^"]*"[^>]*>(.*?)(?:</div>\s*<div|$)',
        html,
        re.DOTALL,
    )
    if not m:
        m = re.search(r'<hr/>\s*<h2>name:\s*\S+', html)
        if m:
            start = m.start()
            end_markers = ['Content curated', 'User Rating', 'USER RATING', 'Grade ']
            end = len(html)
            for marker in end_markers:
                pos = html.find(marker, start)
                if pos != -1 and pos < end:
                    end = pos
            raw = html[start:end]
        else:
            return None
    else:
        raw = m.group(1)

    raw = re.sub(r"<[^>]+>", "\n", raw)
    raw = raw.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    raw = raw.replace("&quot;", '"').replace("&#39;", "'")

    lines = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped:
            lines.append(stripped)

    text = "\n".join(lines)

    # Reconstruct frontmatter
    fm_match = re.search(r'name:\s*(\S+)\s+description:\s*(.+?)(?=\n\w|\n#|\Z)', text, re.DOTALL)
    if fm_match:
        name = fm_match.group(1).strip()
        desc = fm_match.group(2).strip()
        body_start = fm_match.end()
        body = text[body_start:].strip()
        return f"---\nname: {name}\ndescription: >\n  {desc}\n---\n\n{body}"

    return text if len(text) > 50 else None


def install_skill(
    skill_id: str,
    *,
    target_dir: str | None = None,
    skill_md_override: str | None = None,
) -> str:
    """Download and install a skill from SkillHub into the local skills directory.

    Returns the path to the installed skill directory.
    """
    if target_dir is None:
        from .. import config as _cfg
        target_dir = os.path.join(str(_cfg.PYTHONCLAW_HOME), "context", "skills")

    detail = None
    if not skill_md_override:
        detail = get_skill_detail(skill_id)
        if not detail:
            raise RuntimeError(f"Could not fetch skill '{skill_id}' from SkillHub.")

    skill_md = skill_md_override or detail.get("skill_md", "")
    if not skill_md:
        raise RuntimeError(f"No SKILL.md content found for '{skill_id}'.")

    skill_name = _derive_skill_name(skill_id, skill_md, detail)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", skill_name).strip("_")
    if not safe_name:
        safe_name = "imported_skill"

    category = "skillhub"
    skill_dir = os.path.join(target_dir, category, safe_name)
    os.makedirs(skill_dir, exist_ok=True)

    md_path = os.path.join(skill_dir, "SKILL.md")

    if not skill_md.startswith("---"):
        skill_md = f"---\nname: {safe_name}\ndescription: Imported from SkillHub ({skill_id})\n---\n\n{skill_md}"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(skill_md + "\n")

    source_url = detail.get("source_url", f"{SKILL_PAGE_BASE}/{skill_id}") if detail else f"{SKILL_PAGE_BASE}/{skill_id}"
    meta_path = os.path.join(skill_dir, ".skillhub.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"id": skill_id, "source": source_url, "installed_by": "pythonclaw"}, f, indent=2)

    return skill_dir


def _derive_skill_name(skill_id: str, skill_md: str, detail: dict | None) -> str:
    """Extract a reasonable skill name from available data."""
    name_match = re.search(r"^name:\s*(.+)$", skill_md, re.MULTILINE)
    if name_match:
        return name_match.group(1).strip()
    if detail and detail.get("name"):
        return detail["name"]
    parts = skill_id.rsplit("-", 1)
    return parts[-1] if parts else skill_id


def format_search_results(results: list[dict]) -> str:
    """Format search results for CLI display."""
    if not results:
        return "No skills found."

    lines = []
    for i, r in enumerate(results, 1):
        name = r.get("name", r.get("title", "???"))
        desc = r.get("description", "")[:80]
        sid = r.get("id", r.get("slug", ""))
        score = r.get("score", r.get("ai_score", ""))
        stars = r.get("stars", "")

        header = f"  {i}. {name}"
        if score:
            header += f"  (score: {score})"
        if stars:
            header += f"  ★{stars}"

        lines.append(header)
        if desc:
            lines.append(f"     {desc}")
        if sid:
            lines.append(f"     ID: {sid}")
        lines.append("")

    return "\n".join(lines)
