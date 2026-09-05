"""Check that public routes serve the checked-out HTML, not a fallback home."""

import argparse
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ("", "controle-remoto-samsung-smart-tv-4k/", "ureia-agricola-46-nitrogenio-1kg/")


def normalize(text):
    return text.replace("\r\n", "\n").rstrip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://cadindetudo-site.pages.dev")
    args = parser.parse_args()
    failures = 0
    for route in ROUTES:
        url = args.base_url.rstrip("/") + "/" + route
        try:
            expected = (ROOT / route / "index.html").read_text(encoding="utf-8")
            request = Request(url, headers={"User-Agent": "Cadin-Deploy-Check/1.0"})
            with urlopen(request, timeout=30) as response:
                actual = response.read().decode("utf-8")
                if response.status != 200 or normalize(actual) != normalize(expected):
                    raise ValueError(f"HTTP {response.status}; HTML differs from checkout")
            print(f"OK 200, HTML matches: {url}")
        except (URLError, OSError, ValueError) as error:
            failures += 1
            print(f"FAIL {url}: {error}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
