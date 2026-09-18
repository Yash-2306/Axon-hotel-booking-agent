import subprocess
import sys

def install_playwright_browsers():
    """Install playwright chromium browser on Streamlit Cloud."""
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
            check=True,
            capture_output=True
        )
    except Exception:
        pass  # Already installed or not available

install_playwright_browsers()
