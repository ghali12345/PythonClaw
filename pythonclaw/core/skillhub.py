"""
Skill marketplace client for PythonClaw.

Primary source: ClawHub (https://topclawhubskills.com/api) — the OpenClaw
public skills registry.  Free, no API key required, 13K+ skills.

All endpoints are unauthenticated and return JSON directly.

Available ClawHub endpoints
---------------------------
  GET /api/search?q=TERM   — free-text search
  GET /api/top-downloads   — most downloaded skills
  GET /api/top-stars       — most starred skills
  GET /api/newest          — recently published skills
  GET /api/certified       — security-verified skills
  GET /api/stats           — platform statistics
  GET /api/health          — API status
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

CLAWHUB_API = "https://topclawhubskills.com/api"
CLAWHUB_WEB = "https://clawhub.com"


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


def _api_get(path: str, params: dict[str, Any] | None = None) -> dict:
    """Make a GET request to the ClawHub API (no auth required)."""
    url = f"{CLAWHUB_API}{path}"
    if params:
        qs = "&".join(
            f"{k}={urllib.request.quote(str(v))}"
            for k, v in params.items() if v is not None
        )
        if qs:
            url = f"{url}?{qs}"

    headers = {"User-Agent": "PythonClaw/1.0", "Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=15, context=_get_ssl_ctx()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        logger.warning("ClawHub API error %s: %s", exc.code, err_body)
        raise RuntimeError(f"ClawHub API error ({exc.code}): {err_body}") from exc
    except Exception as exc:
        raise RuntimeError(f"ClawHub request failed: {exc}") from exc


def _normalize(skills: list[dict]) -> list[dict]:
    """Normalize ClawHub skill records to a consistent format."""
    results: list[dict] = []
    for s in skills:
        results.append({
            "id": s.get("slug", ""),
            "name": s.get("display_name", s.get("slug", "")),
            "description": s.get("summary", "")[:160],
            "author": s.get("owner_handle", ""),
            "downloads": s.get("downloads", 0),
            "stars": s.get("stars", 0),
            "certified": s.get("is_certified", False),
            "source_url": f"{CLAWHUB_WEB}/skills/{s.get('slug', '')}",
        })
    return results


# ── Public API ────────────────────────────────────────────────────────────────

def search(query: str, *, limit: int = 10, **_kwargs: Any) -> list[dict]:
    """Search ClawHub for skills matching a query."""
    result = _api_get("/search", params={"q": query})
    data = result.get("data", [])
    return _normalize(data[:limit])


def browse(
    *,
    limit: int = 20,
    sort: str = "score",
    **_kwargs: Any,
) -> list[dict]:
    """Browse the ClawHub catalog.

    *sort* maps to ClawHub endpoints:
      - "score" / "downloads" → /top-downloads
      - "stars"               → /top-stars
      - "recent" / "newest"   → /newest
      - "certified"           → /certified
    """
    endpoint_map = {
        "score": "/top-downloads",
        "downloads": "/top-downloads",
        "composite": "/top-downloads",
        "stars": "/top-stars",
        "recent": "/newest",
        "newest": "/newest",
        "certified": "/certified",
    }
    endpoint = endpoint_map.get(sort, "/top-downloads")
    result = _api_get(endpoint)
    data = result.get("data", [])
    return _normalize(data[:limit])


def get_skill_detail(skill_id: str) -> dict | None:
    """Fetch detail for a skill.

    ClawHub search results already contain summary info.  For full
    instructions, the skill must be installed (``clawhub install``).
    We return whatever metadata we have from the listing.
    """
    try:
        result = _api_get("/search", params={"q": skill_id})
        data = result.get("data", [])
        for s in data:
            if s.get("slug") == skill_id:
                normalized = _normalize([s])[0]
                normalized["skill_md"] = _build_skill_md(s)
                return normalized

        if data:
            s = data[0]
            normalized = _normalize([s])[0]
            normalized["skill_md"] = _build_skill_md(s)
            return normalized
    except Exception as exc:
        logger.warning("ClawHub detail fetch failed for '%s': %s", skill_id, exc)

    return None


def stats() -> dict:
    """Get ClawHub platform statistics."""
    result = _api_get("/stats")
    return result.get("data", result)


def verify_api() -> dict:
    """Verify ClawHub API is reachable (no key needed).

    Returns ``{"ok": True, ...}`` on success.
    """
    try:
        result = _api_get("/health")
        if result.get("ok"):
            count = result.get("skill_count", "?")
            return {
                "ok": True,
                "message": f"ClawHub API is online ({count} skills available).",
            }
        return {"ok": False, "error": "Unexpected response from ClawHub API."}
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}


# ── Install ───────────────────────────────────────────────────────────────────

def _build_skill_md(skill: dict) -> str:
    """Build a SKILL.md from ClawHub metadata."""
    name = skill.get("display_name", skill.get("slug", "unknown"))
    slug = skill.get("slug", "")
    summary = skill.get("summary", "No description.")
    author = skill.get("owner_handle", "")
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower()).strip("_")

    lines = [
        "---",
        f"name: {safe_name}",
        "description: >",
        f"  {summary}",
        "---",
        "",
        f"# {name}",
        "",
    ]
    if author:
        lines.append(f"*By @{author} on ClawHub*")
        lines.append("")
    lines.append(f"Source: {CLAWHUB_WEB}/skills/{slug}")
    lines.append("")
    lines.append("## Instructions")
    lines.append("")
    lines.append(f"This skill was imported from ClawHub (`{slug}`).")
    lines.append("Refer to the source page for full documentation and usage instructions.")
    lines.append("")
    if summary:
        lines.append("## Description")
        lines.append("")
        lines.append(summary)
        lines.append("")

    return "\n".join(lines)


def install_skill(
    skill_id: str,
    *,
    target_dir: str | None = None,
    skill_md_override: str | None = None,
) -> str:
    """Download and install a skill from ClawHub into the local skills directory.

    Returns the path to the installed skill directory.
    """
    if target_dir is None:
        from .. import config as _cfg
        target_dir = os.path.join(str(_cfg.PYTHONCLAW_HOME), "context", "skills")

    detail = None
    if not skill_md_override:
        detail = get_skill_detail(skill_id)
        if not detail:
            raise RuntimeError(f"Could not fetch skill '{skill_id}' from ClawHub.")

    skill_md = skill_md_override or detail.get("skill_md", "")
    if not skill_md:
        raise RuntimeError(f"No SKILL.md content found for '{skill_id}'.")

    skill_name = _derive_skill_name(skill_id, skill_md, detail)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", skill_name).strip("_")
    if not safe_name:
        safe_name = "imported_skill"

    category = "clawhub"
    skill_dir = os.path.join(target_dir, category, safe_name)
    os.makedirs(skill_dir, exist_ok=True)

    md_path = os.path.join(skill_dir, "SKILL.md")
    if not skill_md.startswith("---"):
        skill_md = f"---\nname: {safe_name}\ndescription: Imported from ClawHub ({skill_id})\n---\n\n{skill_md}"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(skill_md + "\n")

    fallback_url = f"{CLAWHUB_WEB}/skills/{skill_id}"
    source_url = detail.get("source_url", fallback_url) if detail else fallback_url
    meta_path = os.path.join(skill_dir, ".clawhub.json")
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
        downloads = r.get("downloads", "")
        stars = r.get("stars", "")
        certified = r.get("certified", False)

        header = f"  {i}. {name}"
        if downloads:
            header += f"  ↓{downloads:,}" if isinstance(downloads, int) else f"  ↓{downloads}"
        if stars:
            header += f"  ★{stars}"
        if certified:
            header += "  ✓certified"

        lines.append(header)
        if desc:
            lines.append(f"     {desc}")
        if sid:
            lines.append(f"     ID: {sid}")
        lines.append("")

    return "\n".join(lines)
