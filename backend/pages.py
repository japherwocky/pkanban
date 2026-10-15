"""The <head> of the web app's public pages, and the files crawlers ask for.

The web app renders in the browser, so every URL used to arrive with the same
title and description, the ones in index.html. Google runs the script and
sees a page's own title eventually; link previews (Slack, iMessage, X) and
most other crawlers never run it, so they saw "pkanban" and the tagline for
every page. Now the server writes each public page's title, description,
social-preview tags and canonical URL into the HTML itself.

The titles live here only. index.html also carries them as JSON, which the
app reads to keep the tab title right as you navigate (pageTitle.js), so no
page repeats its own. Docs pages take theirs from their markdown's first
heading, on both sides, so those cannot drift either.

robots.txt and sitemap.xml are built per request, from the URL the request
came in on, like the installers: a self-hosted server lists itself.
"""

import html
import json
import os
import re
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

DOCS_PATH = os.path.join(os.path.dirname(__file__), "..", "docs")

PAGES = {
    "/": {
        "title": "pkanban — give your AI a to-do list you can both see",
        "description": (
            "A kanban board your AI reads and updates as it works, and you watch "
            "in your browser. Works with Claude Code, Codex, opencode, or any AI "
            "that can run commands."
        ),
    },
    "/pricing": {
        "title": "Pricing — pkanban",
        "description": "Two plans. The limits count what you own, not who you work with.",
    },
    "/about": {
        "title": "About pkanban",
        "description": (
            "Building the kanban tool we wanted for orchestrating human and AI "
            "agent workflows."
        ),
    },
    "/contact": {
        "title": "Contact — pkanban",
        "description": (
            "Questions, integration ideas, or an enterprise deployment: here's how "
            "to reach us."
        ),
    },
    "/privacy": {
        "title": "Privacy Policy — pkanban",
        "description": "What pkanban collects, why, and what it does with it.",
    },
    "/terms": {
        "title": "Terms of Service — pkanban",
        "description": "The terms for using pkanban.",
    },
    "/connect/claude": {
        "title": "Connect pkanban to Claude — a kanban board Claude can read and update",
        "description": (
            "Add pkanban to Claude as a custom connector. Claude reads your boards, "
            "adds and moves cards as it works, and you see every change on the board."
        ),
    },
}

# The <meta> tags index.html carries, and which value each one takes.
META_TAGS = [
    ("name", "description", "description"),
    ("property", "og:title", "title"),
    ("property", "og:description", "description"),
    ("property", "og:url", "url"),
    ("name", "twitter:title", "title"),
    ("name", "twitter:description", "description"),
]

# Signed-in areas and machinery: nothing there for a search engine.
DISALLOWED = [
    "/api/",
    "/oauth/",
    "/mcp",
    "/boards",
    "/settings",
    "/admin",
    "/organizations",
    "/invite/",
    "/device",
]

# Where the social-preview image is served (main.py), at the root, where
# link previews look for it.
OG_IMAGE_PATH = "/og-image.png"

DOC_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
DESCRIPTION_LIMIT = 160


def _doc_file(path: str) -> Optional[str]:
    """The markdown file behind a docs URL, or None if it is not one."""
    parts = path.strip("/").split("/")
    if parts[0] != "docs" or len(parts) > 3:
        return None
    if len(parts) == 1:
        parts = ["docs", "docs"]
    if not all(DOC_NAME.match(part) for part in parts[1:]):
        return None
    if len(parts) == 3 and parts[1] != "commands":
        return None
    file = os.path.join(DOCS_PATH, *parts[1:]) + ".md"
    return file if os.path.isfile(file) else None


def _plain(markdown: str) -> str:
    """Markdown inline text as plain text: links to their words, no marks."""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", markdown)
    text = re.sub(r"[`*_]", "", text)
    return " ".join(text.split())


def doc_title(markdown: str) -> Optional[str]:
    """A docs page's title: its first heading, which Docs.svelte also uses."""
    for line in markdown.splitlines():
        if line.startswith("# "):
            heading = _plain(line[2:])
            return heading if "pkanban" in heading.lower() else f"{heading} — pkanban docs"
    return None


def _doc_description(markdown: str) -> str:
    """The first paragraph of prose under the heading, cut to a snippet."""
    paragraph = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith(("#", "-", "*", "|", ">", "```", "<")) or re.match(
            r"\d+\.", stripped
        ):
            if paragraph:
                break
            continue
        paragraph.append(stripped)
    text = _plain(" ".join(paragraph))
    if len(text) <= DESCRIPTION_LIMIT:
        return text
    return text[: DESCRIPTION_LIMIT - 1].rsplit(" ", 1)[0] + "…"


def head_for(path: str) -> Optional[dict]:
    """{"title", "description"} for a public page, or None for any other."""
    path = path.rstrip("/") or "/"
    if path in PAGES:
        return PAGES[path]
    doc = _doc_file(path)
    if doc is None:
        return None
    with open(doc, encoding="utf-8") as f:
        markdown = f.read()
    title = doc_title(markdown)
    return {"title": title, "description": _doc_description(markdown)} if title else None


def _set_meta(page: str, attr: str, name: str, value: str) -> str:
    """`page` with one <meta>'s content replaced by `value` (already escaped)."""
    # index.html wraps some of these over several lines, hence \s+.
    return re.sub(
        rf'(<meta\s+{attr}="{re.escape(name)}"\s+content=")[^"]*(")',
        lambda m: f"{m.group(1)}{value}{m.group(2)}",
        page,
        count=1,
    )


def page_html(template: str, path: str, base_url: str) -> str:
    """index.html for `path`: its own <head> if it is public, and the titles
    the app needs to keep the tab title right as it navigates."""
    default_title = re.search(r"<title>(.*?)</title>", template, re.S)
    titles = {
        "default": html.unescape(default_title.group(1)) if default_title else "pkanban",
        "pages": {p: page["title"] for p, page in PAGES.items()},
    }
    # Inside <script>, "</" would end the element early.
    titles_json = json.dumps(titles, ensure_ascii=False).replace("</", "<\\/")
    out = template.replace(
        "</head>",
        f'  <script type="application/json" id="page-titles">{titles_json}</script>\n  </head>',
        1,
    )
    # The preview image, on every page and from this server: index.html names
    # the hosted one, which a self-hosted server should not advertise.
    image = html.escape(f"{base_url.rstrip('/')}{OG_IMAGE_PATH}")
    for attr, name in (("property", "og:image"), ("name", "twitter:image")):
        out = _set_meta(out, attr, name, image)

    head = head_for(path)
    if head is None:
        return out
    values = {
        "title": html.escape(head["title"]),
        "description": html.escape(head["description"]),
        "url": html.escape(f"{base_url.rstrip('/')}{path.rstrip('/') or '/'}"),
    }
    out = re.sub(
        r"<title>.*?</title>",
        lambda _: f"<title>{values['title']}</title>",
        out,
        count=1,
        flags=re.S,
    )
    for attr, name, key in META_TAGS:
        out = _set_meta(out, attr, name, values[key])
    return out.replace(
        "</head>", f'  <link rel="canonical" href="{values["url"]}" />\n  </head>', 1
    )


def public_paths() -> list:
    """Every public page: the ones listed above, then every docs page."""
    paths = list(PAGES)
    paths.append("/docs")
    for name in sorted(os.listdir(DOCS_PATH)):
        stem, ext = os.path.splitext(name)
        if ext == ".md" and stem != "docs" and DOC_NAME.match(stem):
            paths.append(f"/docs/{stem}")
    commands = os.path.join(DOCS_PATH, "commands")
    if os.path.isdir(commands):
        for name in sorted(os.listdir(commands)):
            stem, ext = os.path.splitext(name)
            if ext == ".md" and DOC_NAME.match(stem):
                paths.append(f"/docs/commands/{stem}")
    return paths


def robots_txt(base_url: str) -> str:
    lines = ["User-agent: *", "Allow: /"]
    lines += [f"Disallow: {path}" for path in DISALLOWED]
    lines += ["", f"Sitemap: {base_url.rstrip('/')}/sitemap.xml", ""]
    return "\n".join(lines)


def sitemap_xml(base_url: str) -> str:
    base = base_url.rstrip("/")
    urls = "".join(
        f"  <url><loc>{xml_escape(base + path)}</loc></url>\n" for path in public_paths()
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n"
    )
