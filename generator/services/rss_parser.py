"""Parse RSS/Atom feeds and return a list of article URLs."""
import xml.etree.ElementTree as ET
import requests


def parse_rss_feed(feed_url: str, max_items: int = 20) -> list[str]:
    """
    Fetch and parse an RSS or Atom feed, returning a list of article URLs.

    Works without feedparser (which has build issues) by parsing XML directly.
    """
    headers = {
        "User-Agent": "BlogCopier/1.0 (RSS reader; +https://github.com/blogcopier)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    }
    response = requests.get(feed_url, headers=headers, timeout=15)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    urls: list[str] = []

    # RSS 2.0
    for item in root.findall(".//item"):
        link = item.findtext("link")
        if link and link.startswith("http"):
            urls.append(link.strip())
        if len(urls) >= max_items:
            break

    # Atom
    if not urls:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", ns):
            link_el = entry.find("atom:link[@rel='alternate']", ns) or entry.find("atom:link", ns)
            if link_el is not None:
                href = link_el.get("href", "")
                if href.startswith("http"):
                    urls.append(href.strip())
            if len(urls) >= max_items:
                break

    return urls
