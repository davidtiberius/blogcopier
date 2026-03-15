"""Scrape article text from URLs using requests + BeautifulSoup."""
import logging
import re
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Tags that typically contain boilerplate rather than article content
_NOISE_TAGS = {
    "script", "style", "noscript", "nav", "header", "footer",
    "aside", "form", "button", "svg", "figure",
}

# CSS class/id keywords that signal navigation / sidebar / ad content
# Use word boundaries (\b) to avoid false positives like "read" matching "ad"
_NOISE_PATTERNS = re.compile(
    r"\b(nav|menu|sidebar|footer|header|advert|advertisement|cookie|popup|"
    r"social|share|related|comments?|subscribe|newsletter|promo)\b",
    re.IGNORECASE,
)


def _get_text_parts(container, min_len: int = 20) -> list[str]:
    """Extract text parts from headings, paragraphs, and list items."""
    parts = []
    for el in container.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        text = el.get_text(separator=" ", strip=True)
        if len(text) >= min_len:
            parts.append(text)
    return parts


def _extract_text(soup: BeautifulSoup) -> str:
    """Extract meaningful article text from a parsed HTML document."""
    # Remove noise tags
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    # Remove elements whose class/id looks like boilerplate
    for el in soup.find_all(True):
        if el.parent is None:
            # Already decomposed (e.g. child of a previously removed element)
            continue
        classes = " ".join(el.get("class", []))
        el_id = el.get("id", "")
        if _NOISE_PATTERNS.search(classes) or _NOISE_PATTERNS.search(el_id):
            el.decompose()

    # Try to find the main content container
    container = (
        soup.find("article")
        or soup.find("main")
        or soup.find(class_=re.compile(r"(article|post|content|entry|body)", re.I))
        or soup.find("div", id=re.compile(r"(article|post|content|entry|body)", re.I))
    )

    if container:
        parts = _get_text_parts(container)
        if parts:
            return "\n\n".join(parts)

    # Fallback: try body with a lower minimum length threshold
    body = soup.body
    if body is None:
        return ""

    parts = _get_text_parts(body, min_len=15)
    if parts:
        return "\n\n".join(parts)

    # Last resort: grab all visible text from body
    text = body.get_text(separator="\n", strip=True)
    # Filter out very short lines (likely menu items, buttons, etc.)
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 20]
    return "\n\n".join(lines)


def scrape_article(url: str) -> dict | None:
    """
    Scrape a single article URL.

    Returns a dict with 'url', 'title', and 'text', or None on failure.
    """
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None

    content_type = resp.headers.get("Content-Type", "")
    if "html" not in content_type and "text" not in content_type:
        logger.warning("Skipping non-HTML URL: %s (Content-Type: %s)", url, content_type)
        return None

    soup = BeautifulSoup(resp.content, "lxml")

    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    og_title = soup.find("meta", property="og:title")
    if og_title:
        title = og_title.get("content", title).strip()

    text = _extract_text(soup)
    if len(text) < 100:
        logger.warning("Too little text extracted from %s (%d chars)", url, len(text))
        return None

    # Truncate very long articles to keep token usage reasonable
    MAX_CHARS = 8_000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[... article truncated for analysis ...]"

    return {"url": url, "title": title, "text": text}


def scrape_articles(urls: list[str]) -> list[dict]:
    """Scrape multiple article URLs and return successfully scraped results."""
    results = []
    for url in urls:
        article = scrape_article(url)
        if article:
            results.append(article)
    return results
