import os
import re
from crewai.tools import tool
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from html2text import html2text


STEALTH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


def _clean_and_trim(raw_html: str, max_chars: int = 12000) -> str:
    """Convert HTML to readable markdown and trim to token-safe length."""
    text = html2text(raw_html)
    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove lines that are only dashes/stars (table separators)
    text = re.sub(r'^\s*[-*]{4,}\s*$', '', text, flags=re.MULTILINE)
    return text[:max_chars]


@tool("Stealth Web Browser")
def stealth_browser(url: str) -> str:
    """
    Loads a webpage using a local stealth Playwright browser to bypass basic bot detection.
    Use this to browse live hotel search results from Kayak or any travel site.
    Returns the page content as clean readable text (markdown-formatted).

    :param url: The full URL to browse (e.g. a Kayak hotel search URL)
    :return: Clean text content of the page suitable for hotel extraction
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--window-size=1920,1080",
                ]
            )
            context = browser.new_context(
                extra_http_headers=STEALTH_HEADERS,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                java_script_enabled=True,
            )
            # Remove webdriver property to avoid bot detection
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                # Give JS-rendered content time to load
                page.wait_for_timeout(8000)
                content = page.content()
            except PlaywrightTimeout:
                content = page.content()  # Return whatever loaded
            finally:
                browser.close()

            return _clean_and_trim(content)

    except Exception as e:
        return f"Browser error: {str(e)}. The site may be blocking automated access. Try a different date or location."
