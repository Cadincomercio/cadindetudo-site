from __future__ import annotations

import argparse
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def _request(url: str, *, accept: str = "application/json") -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; CadinSEO/1.0; +https://cadindetudo.com)",
        "Accept": accept,
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
    }
    token = os.getenv("MELI_ACCESS_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=12) as response:
        return response.read()


def _valid_image_url(value: object) -> str:
    url = str(value or "").strip()
    if not url.startswith("https://"):
        return ""
    if "mlstatic.com" not in url and "mercadolibre" not in url:
        return ""
    return url


def _image_from_item_body(body: dict) -> str:
    pictures = body.get("pictures") or []
    if pictures and isinstance(pictures[0], dict):
        for field in ("secure_url", "url"):
            candidate = _valid_image_url(pictures[0].get(field))
            if candidate:
                return candidate
    for field in ("secure_thumbnail", "thumbnail"):
        candidate = _valid_image_url(body.get(field))
        if candidate:
            return candidate
    return ""


def image_from_items_api(item_id: str) -> str:
    if not re.fullmatch(r"MLB\d{6,}", item_id):
        return ""
    try:
        body = json.loads(_request(f"https://api.mercadolibre.com/items/{item_id}").decode("utf-8"))
        return _image_from_item_body(body)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return ""


def _seller_id_from_url(url: str) -> str:
    try:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        seller = (query.get("pdp_filters") or query.get("seller_id") or [""])[0]
        match = re.search(r"seller_id[:=](\d+)", seller)
        if match:
            return match.group(1)
        if str(seller).isdigit():
            return str(seller)
    except Exception:
        pass
    return ""


def image_from_public_search(product: dict) -> str:
    title = str(product.get("title") or "").strip()
    item_id = str(product.get("item_id") or "").strip()
    canonical = str(product.get("canonical_url") or product.get("source_url") or "")
    seller_id = _seller_id_from_url(canonical)
    if not title:
        return ""

    params = {"q": title, "limit": "50"}
    if seller_id:
        params["seller_id"] = seller_id
    url = "https://api.mercadolibre.com/sites/MLB/search?" + urllib.parse.urlencode(params)
    try:
        body = json.loads(_request(url).decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return ""

    results = body.get("results") or []
    if not isinstance(results, list):
        return ""

    ordered = sorted(
        [r for r in results if isinstance(r, dict)],
        key=lambda r: 0 if str(r.get("id") or "") == item_id else 1,
    )
    for result in ordered:
        candidate = _image_from_item_body(result)
        if candidate:
            return candidate
    return ""


def image_from_product_page(url: str) -> str:
    if not url.startswith("https://") or "mercadolivre.com" not in url:
        return ""
    try:
        text = _request(url, accept="text/html,application/xhtml+xml").decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return ""

    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'"secure_url"\s*:\s*"(https:[^"\\]+)"',
        r'"url"\s*:\s*"(https:[^"\\]+mlstatic\.com[^"\\]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = html.unescape(match.group(1)).replace("\\/", "/")
            candidate = _valid_image_url(candidate)
            if candidate:
                return candidate
    return ""


def enrich(path: Path) -> bool:
    job = json.loads(path.read_text(encoding="utf-8"))
    product = job.get("product") or {}

    if _valid_image_url(product.get("image_url")):
        print("Imagem do produto já informada no job; nenhuma alteração necessária.")
        return False

    item_id = str(product.get("item_id") or "").strip()
    image = image_from_items_api(item_id) if item_id else ""
    if image:
        print("Imagem resolvida via Items API.")

    if not image:
        image = image_from_public_search(product)
        if image:
            print("Imagem resolvida via busca pública do Mercado Livre.")

    if not image:
        page_url = str(product.get("canonical_url") or product.get("source_url") or "").strip()
        image = image_from_product_page(page_url)
        if image:
            print("Imagem resolvida via metadados da página do produto.")

    if not image:
        print("Não foi possível resolver uma imagem real e confiável; mantendo image_url vazio.")
        return False

    product["image_url"] = image
    job["product"] = product
    path.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imagem real do produto resolvida: {image}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    path = Path(args.job)
    if not path.exists():
        raise SystemExit(f"Job não encontrado: {path}")
    enrich(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
