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
    url = str(value or "").strip().replace("\\/", "/")
    if not url.startswith("https://"):
        return ""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "mlstatic.com" not in host and "mercadolibre" not in host and "mercadolivre" not in host:
        return ""
    blocked_fragments = (
        "/frontend-assets/", "suspicious-traffic", "/navigation/", "/polyfills/",
        "/ui-navigation/", "/fonts/", "/icons/", "/logos/", "/brand/",
    )
    if any(fragment in path for fragment in blocked_fragments):
        return ""
    # Fotos de produto do CDN do Mercado Livre normalmente usam D_NQ_* ou extensão de imagem.
    if host.endswith("mlstatic.com") and not any(token in path for token in ("d_nq_", ".jpg", ".jpeg", ".png", ".webp", ".avif")):
        return ""
    return url


def _dedupe(values: list[str], limit: int = 8) -> list[str]:
    out, seen = [], set()
    for value in values:
        url = _valid_image_url(value)
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(url)
        if len(out) >= limit:
            break
    return out


def _images_from_item_body(body: dict) -> list[str]:
    found = []
    for key in ("pictures", "images", "gallery"):
        pictures = body.get(key) or []
        if isinstance(pictures, list):
            for picture in pictures:
                if isinstance(picture, str):
                    found.append(picture)
                    continue
                if not isinstance(picture, dict):
                    continue
                for field in ("secure_url", "url", "src", "secureUrl"):
                    candidate = _valid_image_url(picture.get(field))
                    if candidate:
                        found.append(candidate)
                        break
    for field in ("secure_thumbnail", "thumbnail", "picture", "image"):
        candidate = _valid_image_url(body.get(field))
        if candidate:
            found.append(candidate)
    # Alguns endpoints encapsulam dados do produto.
    for field in ("product", "item", "data"):
        nested = body.get(field)
        if isinstance(nested, dict):
            found.extend(_images_from_item_body(nested))
    return _dedupe(found)


def _json_images(url: str) -> list[str]:
    try:
        body = json.loads(_request(url).decode("utf-8"))
        return _images_from_item_body(body) if isinstance(body, dict) else []
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return []


def images_from_items_api(item_id: str) -> list[str]:
    if not re.fullmatch(r"MLB\d{6,}", item_id):
        return []
    return _json_images(f"https://api.mercadolibre.com/items/{item_id}")


def _mlbu_from_product(product: dict) -> str:
    for value in (product.get("source_url"), product.get("canonical_url")):
        match = re.search(r"(?:/up/|\b)(MLBU\d{6,})", str(value or ""), re.I)
        if match:
            return match.group(1).upper()
    return ""


def images_from_public_product_ids(product: dict) -> list[str]:
    """Tenta rotas públicas ligadas ao identificador MLBU sem autenticar conta do vendedor."""
    mlbu = _mlbu_from_product(product)
    if not mlbu:
        return []
    endpoints = [
        f"https://api.mercadolibre.com/products/{mlbu}",
        f"https://api.mercadolibre.com/user-products/{mlbu}",
    ]
    for endpoint in endpoints:
        images = _json_images(endpoint)
        if images:
            return images
    return []


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


def images_from_public_search(product: dict) -> list[str]:
    title = str(product.get("title") or "").strip()
    item_id = str(product.get("item_id") or "").strip()
    canonical = str(product.get("canonical_url") or product.get("source_url") or "")
    seller_id = _seller_id_from_url(canonical)
    if not title:
        return []
    params = {"q": title, "limit": "50"}
    if seller_id:
        params["seller_id"] = seller_id
    url = "https://api.mercadolibre.com/sites/MLB/search?" + urllib.parse.urlencode(params)
    try:
        body = json.loads(_request(url).decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    results = body.get("results") or []
    if not isinstance(results, list):
        return []
    exact = [r for r in results if isinstance(r, dict) and str(r.get("id") or "") == item_id]
    # Segurança: sem correspondência exata do item, não usar imagem de outro vendedor/produto.
    if item_id and not exact:
        return []
    found = []
    for result in exact[:1] if exact else []:
        found.extend(_images_from_item_body(result))
    return _dedupe(found)


def images_from_product_page(url: str) -> list[str]:
    if not url.startswith("https://") or "mercadolivre.com" not in url:
        return []
    try:
        text = _request(url, accept="text/html,application/xhtml+xml").decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return []
    low = text.lower()
    if "suspicious-traffic" in low or "tráfego suspeito" in low or "trafego suspeito" in low:
        return []
    found = []
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'"secure_url"\s*:\s*"(https:[^"\\]+)"',
        r'"url"\s*:\s*"(https:[^"\\]+mlstatic\.com[^"\\]+)"',
        r'(https://[^"\'<>\\ ]+mlstatic\.com[^"\'<>\\ ]+)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            candidate = html.unescape(match.group(1)).replace("\\/", "/")
            candidate = _valid_image_url(candidate)
            if candidate:
                found.append(candidate)
    return _dedupe(found)


def enrich(path: Path) -> bool:
    job = json.loads(path.read_text(encoding="utf-8"))
    product = job.get("product") or {}
    existing_main = _valid_image_url(product.get("main_image_url") or product.get("image_url"))
    existing_gallery = _dedupe(product.get("gallery_images") or [])
    item_id = str(product.get("item_id") or "").strip()
    found = []

    if item_id:
        found = images_from_items_api(item_id)
        if found:
            print(f"Imagens resolvidas via Items API pública: {len(found)}")

    if not found:
        found = images_from_public_product_ids(product)
        if found:
            print(f"Imagens resolvidas via identificador MLBU público: {len(found)}")

    if not found:
        found = images_from_public_search(product)
        if found:
            print(f"Imagens resolvidas via busca pública com correspondência exata: {len(found)}")

    if not found:
        page_url = str(product.get("canonical_url") or product.get("source_url") or "").strip()
        found = images_from_product_page(page_url)
        if found:
            print(f"Imagens resolvidas via metadados da página: {len(found)}")

    combined = _dedupe(([existing_main] if existing_main else []) + existing_gallery + found)
    if not combined:
        print("Não foi possível resolver imagem real e confiável sem autenticação; mantendo campos vazios.")
        return False

    main = existing_main or combined[0]
    gallery = _dedupe([main] + combined)
    changed = False
    for field in ("main_image_url", "image_url"):
        if product.get(field) != main:
            product[field] = main
            changed = True
    if product.get("gallery_images") != gallery:
        product["gallery_images"] = gallery
        changed = True
    if not changed:
        print("As imagens do produto já estavam atualizadas.")
        return False
    job["product"] = product
    path.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imagem principal: {main}")
    print(f"Galeria: {len(gallery)} imagem(ns)")
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
