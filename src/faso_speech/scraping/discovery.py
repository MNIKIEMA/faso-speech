import re
import urllib.parse

from faso_speech.scraping.app_builder import fetch_text


MOOREBURKINA_SITEMAP_URL = "https://mooreburkina.com/fr/sitemap"


def extract_links(document, base_url):
    links = []
    for href in re.findall(r"<a[^>]+href=['\"](?P<href>[^'\"]+)['\"]", document):
        if href.startswith("#") or href.startswith("mailto:"):
            continue
        links.append(urllib.parse.urljoin(base_url, href))
    return links


def is_app_url(url):
    parsed = urllib.parse.urlsplit(url)
    return parsed.netloc == "media.ipsapps.org" and parsed.path.endswith(".html")


def discover_app_urls_from_page(url):
    document = fetch_text(url)
    return [link for link in extract_links(document, url) if is_app_url(link)]


def discover_links_from_sitemap(sitemap_url=MOOREBURKINA_SITEMAP_URL):
    document = fetch_text(sitemap_url)
    return extract_links(document, sitemap_url)


def discover_app_urls_from_sitemap(sitemap_url=MOOREBURKINA_SITEMAP_URL, max_source_pages=None):
    app_urls = []
    source_pages = []

    for link in discover_links_from_sitemap(sitemap_url):
        if is_app_url(link):
            app_urls.append(link)
            continue
        if "mooreburkina.com" not in urllib.parse.urlsplit(link).netloc:
            continue
        source_pages.append(link)

    if max_source_pages:
        source_pages = source_pages[:max_source_pages]

    for source_url in source_pages:
        try:
            app_urls.extend(discover_app_urls_from_page(source_url))
        except Exception as error:
            print(f"warning: failed to discover app links from {source_url}: {error}")

    return sorted(set(app_urls))
