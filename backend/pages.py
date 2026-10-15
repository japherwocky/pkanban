"""The <head> of public pages people should be able to find from outside.

The web app renders in the browser, so every URL used to arrive with the same
title and description, the ones in index.html. Google runs the script and
sees the page's own title eventually; link previews (Slack, iMessage, X) and
most other crawlers never run it, so they saw "pkanban" and the tagline for
every page. A page listed here is served with its own title, description,
social-preview tags and canonical URL already in the HTML.

The page sets the same title in its <svelte:head>, for navigation inside the
app. Keep the two in step.
"""

import html
import re
from typing import Optional

PAGES = {
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


def page_html(template: str, path: str, base_url: str) -> Optional[str]:
    """index.html with `path`'s own <head>, or None if it has none."""
    page = PAGES.get(path.rstrip("/") or "/")
    if page is None:
        return None
    values = {
        "title": html.escape(page["title"]),
        "description": html.escape(page["description"]),
        "url": html.escape(f"{base_url.rstrip('/')}{path}"),
    }
    out = re.sub(
        r"<title>.*?</title>",
        lambda _: f"<title>{values['title']}</title>",
        template,
        count=1,
        flags=re.S,
    )
    for attr, name, key in META_TAGS:
        # index.html wraps some of these over several lines, hence \s+.
        out = re.sub(
            rf'(<meta\s+{attr}="{re.escape(name)}"\s+content=")[^"]*(")',
            lambda m: f"{m.group(1)}{values[key]}{m.group(2)}",
            out,
            count=1,
        )
    return out.replace(
        "</head>", f'  <link rel="canonical" href="{values["url"]}" />\n  </head>', 1
    )
