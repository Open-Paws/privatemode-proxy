#!/usr/bin/env python3
"""
Scrape Privatemode documentation and save as markdown files.
"""

import os
import re

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib.parse import urljoin, urlparse

BASE_URL = "https://docs.privatemode.ai"
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")

# Pages to scrape (will discover more from navigation)
SEED_URLS = [
    "/",
    "/getting-started",
    "/chat-completions",
    "/tool-calling",
    "/proxy-configuration",
    "/verification-from-source-code",
]

visited = set()
pages = {}


def get_page(url: str) -> BeautifulSoup | None:
    """Fetch and parse a page."""
    try:
        full_url = urljoin(BASE_URL, url)
        if full_url in visited:
            return None
        visited.add(full_url)

        print(f"Fetching: {full_url}")
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def extract_nav_links(soup: BeautifulSoup) -> list[str]:
    """Extract navigation links from the page."""
    links = []
    # Look for sidebar navigation
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('/') and not href.startswith('//'):
            if not any(x in href for x in ['#', 'mailto:', 'javascript:']):
                links.append(href)
    return list(set(links))


def extract_content(soup: BeautifulSoup) -> tuple[str, str]:
    """Extract main content from the page."""
    # Try to find main content area
    main = soup.find('main') or soup.find('article') or soup.find(class_=re.compile(r'content|docs|markdown'))

    if not main:
        # Fallback: try to find the largest div with text
        main = soup.find('body')

    if not main:
        return "", ""

    # Get title
    title = ""
    h1 = main.find('h1')
    if h1:
        title = h1.get_text(strip=True)
    else:
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True).split('|')[0].strip()

    # Remove navigation, footer, etc.
    for tag in main.find_all(['nav', 'footer', 'header', 'script', 'style']):
        tag.decompose()

    # Convert to markdown
    content = md(str(main), heading_style="ATX", code_language_callback=lambda el: "python" if "python" in str(el).lower() else "bash")

    # Clean up markdown
    content = re.sub(r'\n{3,}', '\n\n', content)
    content = content.strip()

    return title, content


def url_to_filename(url: str) -> str:
    """Convert URL to filename safely, preventing path traversal attacks."""
    path = urlparse(url).path.strip('/')
    if not path:
        return "index.md"
    # Replace slashes with underscores
    name = path.replace('/', '_')
    # Remove any path traversal attempts and dangerous characters
    # Only allow alphanumeric, underscore, and hyphen (block backslashes too)
    name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    if not name:
        return "index.md"
    return f"{name}.md"


def safe_join_path(base_dir: str, filename: str) -> str:
    """Safely join base directory and filename, preventing path traversal."""
    from pathlib import Path
    # Resolve to absolute paths
    base = Path(base_dir).resolve()
    target = (base / filename).resolve()
    # Ensure the target is within the base directory using pathlib's semantic check
    # which is immune to partial string prefix attacks (e.g. /docs vs /docs_evil)
    if target != base and base not in target.parents:
        raise ValueError(f"Path traversal detected: {filename}")
    return str(target)


def scrape_all():
    """Scrape all documentation pages."""
    to_visit = list(SEED_URLS)

    while to_visit:
        url = to_visit.pop(0)
        soup = get_page(url)
        if not soup:
            continue

        # Extract and save content
        title, content = extract_content(soup)
        if content:
            filename = url_to_filename(url)
            try:
                filepath = safe_join_path(DOCS_DIR, filename)

                with open(filepath, 'w') as f:
                    if title:
                        f.write(f"# {title}\n\n")
                    f.write(content)

                print(f"  Saved: {filename}")
                pages[url] = {'title': title, 'file': filename}
            except (ValueError, requests.RequestException) as e:
                print(f"  Skipping {url}: {e}")
                continue

        # Discover more links
        for link in extract_nav_links(soup):
            if link not in visited and urljoin(BASE_URL, link) not in visited:
                if link.startswith('/') and not link.startswith('//'):
                    to_visit.append(link)

    # Create index
    with open(safe_join_path(DOCS_DIR, "README.md"), 'w') as f:
        f.write("# Privatemode Documentation\n\n")
        f.write("Scraped from https://docs.privatemode.ai\n\n")
        f.write("## Pages\n\n")
        for url, info in sorted(pages.items()):
            f.write(f"- [{info['title'] or url}]({info['file']})\n")

    print(f"\nDone! Scraped {len(pages)} pages to {DOCS_DIR}")


if __name__ == "__main__":
    scrape_all()
