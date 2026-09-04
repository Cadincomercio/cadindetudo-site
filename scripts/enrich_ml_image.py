from __future__ import annotations

import argparse
import difflib
import html
import json
import os
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = REPOSITORY_ROOT / "data" / "ml_images_cache.json"


def _request(url: str, *, accept: str = "application/json") -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0 Safari/537.36",
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
    url = html.unescape(str(value or "").strip()).replace("\\/", "/")
    if not url.startswith("https://"):
        return ""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "mlstatic.com" not in host:
        return ""
    blocked = (
        "/frontend-assets/", "suspicious-traffic", "/navigation/", "/polyfills/",
        "/ui-navigation/", "/fonts/", "/icons/", "/logos/", "/brand/",
    )
    if any(fragment in path for fragment in blocked):
        return ""
    if "d_nq_" not in path and "d_q_np" not in path and not path.endswith((".jpg", ".jpeg", ".png", ".webp", ".avif")):
        return ""
    return url


def _image_key(url: str) -> str:
    """Agrupa versões 2X/N/V/C/T/L/B da mesma foto pelo identificador central."""
    match = re.search(r"(\d+-MLB\d+_\d{6})", url, re.I)
    return match.group(1).lower() if match else url.lower()


def _dedupe(values: list[str], limit: int = 8) -> list[str]:
    out, seen = [], set()
    for value in values:
        url = _valid_image_url(value)
        if not url:
            continue
        key = _image_key(url)
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
        if len(out) >= limit:
            break
    return out


def _load_cache(path: Path = CACHE_PATH) -> dict:
    """Carrega tanto o formato atual (chave por item_id) quanto um cache vazio/antigo."""
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return body if isinstance(body, dict) else {}


def _cache_images(cache: dict, item_id: str) -> tuple[list[str], dict]:
    entry = cache.get(item_id)
    if not isinstance(entry, dict):
        return [], {}
    main = _valid_image_url(entry.get("main_image_url"))
    gallery = entry.get("gallery_images")
    if not isinstance(gallery, list):
        gallery = []
    images = _dedupe(([main] if main else []) + gallery)
    return images, entry


def _save_cache(
    cache: dict,
    product: dict,
    images: list[str],
    source: str,
    path: Path = CACHE_PATH,
) -> None:
    item_id = str(product.get("item_id") or "").strip().upper()
    images = _dedupe(images)
    if not re.fullmatch(r"MLB\d{6,}", item_id) or not images:
        return

    old_images, old_entry = _cache_images(cache, item_id)
    # Uma resolução parcial nunca reduz a galeria persistida anteriormente.
    gallery = old_images if len(old_images) > len(images) else images
    old_main = _valid_image_url(old_entry.get("main_image_url"))
    main = old_main if old_main and len(old_images) > len(images) else gallery[0]
    entry = {
        "title": str(product.get("title") or old_entry.get("title") or "").strip(),
        "mlbu": _mlbu_from_product(product) or str(old_entry.get("mlbu") or "").strip().upper(),
        "main_image_url": main,
        "gallery_images": _dedupe([main] + gallery),
        "source": source,
        "resolved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    cache[item_id] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


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
    mlbu = _mlbu_from_product(product)
    if not mlbu:
        return []
    for endpoint in (
        f"https://api.mercadolibre.com/products/{mlbu}",
        f"https://api.mercadolibre.com/user-products/{mlbu}",
    ):
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
    if item_id and not exact:
        return []
    found = []
    for result in exact[:1] if exact else []:
        found.extend(_images_from_item_body(result))
    return _dedupe(found)


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _title_score(candidate: str, title: str) -> float:
    a, b = _norm(candidate), _norm(title)
    if not a or not b:
        return 0.0
    if a == b or a in b or b in a:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    overlap = len(ta & tb) / max(1, len(tb))
    sequence = difflib.SequenceMatcher(None, a, b).ratio()
    return max(overlap, sequence)


def _urls_from_attrs(tag: str) -> list[str]:
    found = []
    for attr in ("src", "data-src", "data-lazy", "data-original", "srcset"):
        for match in re.finditer(rf"\b{attr}\s*=\s*[\"']([^\"']+)", tag, re.I):
            raw = html.unescape(match.group(1)).replace("\\/", "/")
            parts = [p.strip().split()[0] for p in raw.split(",")] if attr == "srcset" else [raw]
            found.extend(parts)
    return _dedupe(found)


def _listing_urls(title: str) -> list[str]:
    norm = _norm(title)
    slug = re.sub(r"[^a-z0-9]+", "-", norm).strip("-")
    urls = [f"https://lista.mercadolivre.com.br/{slug}"]
    if re.search(r"(?:npk\s*)?0?4[ .-]?14[ .-]?0?8", norm, re.I):
        urls.extend([
            "https://lista.mercadolivre.com.br/npk-04.14.08",
            "https://lista.mercadolivre.com.br/adubo-04-14-08",
            "https://lista.mercadolivre.com.br/adubo-npk-04-14-08",
        ])
    return list(dict.fromkeys(urls))


def images_from_listing_search(product: dict) -> list[str]:
    title = str(product.get("title") or "").strip()
    if not title:
        return []
    for url in _listing_urls(title):
        try:
            text = _request(url, accept="text/html,application/xhtml+xml").decode("utf-8", errors="ignore")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            continue
        low = text.lower()
        if "suspicious-traffic" in low or "tráfego suspeito" in low or "trafego suspeito" in low:
            continue
        scored = []
        for match in re.finditer(r"<img\b[^>]*>", text, re.I | re.S):
            tag = match.group(0)
            alt_match = re.search(r"\b(?:alt|title)\s*=\s*[\"']([^\"']+)", tag, re.I | re.S)
            label = html.unescape(alt_match.group(1)) if alt_match else ""
            score = _title_score(label, title)
            if score >= 0.82:
                for image_url in _urls_from_attrs(tag):
                    scored.append((score, "2x" in image_url.lower(), image_url))
        if scored:
            scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
            return _dedupe([row[2] for row in scored])
    return []


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
            candidate = _valid_image_url(html.unescape(match.group(1)).replace("\\/", "/"))
            if candidate:
                found.append(candidate)
    return _dedupe(found)


def enrich(path: Path, cache_path: Path = CACHE_PATH) -> bool:
    job = json.loads(path.read_text(encoding="utf-8"))
    product = job.get("product") or {}
    existing_main = _valid_image_url(product.get("main_image_url") or product.get("image_url"))
    existing_gallery = _dedupe(product.get("gallery_images") or [])
    item_id = str(product.get("item_id") or "").strip().upper()
    cache = _load_cache(cache_path)
    found = []
    source = ""
    if item_id:
        found, _ = _cache_images(cache, item_id)
        if found:
            source = "cache"
            print(f"Cache hit para {item_id}: {len(found)} imagem(ns); consultas de rede ignoradas.")
    if not found and item_id:
        found = images_from_items_api(item_id)
        if found:
            source = "items_api"
            print(f"Imagens resolvidas via Items API pública: {len(found)}")
    if not found:
        found = images_from_public_product_ids(product)
        if found:
            source = "public_product_id"
            print(f"Imagens resolvidas via identificador MLBU público: {len(found)}")
    if not found:
        found = images_from_public_search(product)
        if found:
            source = "public_search"
            print(f"Imagens resolvidas via busca pública com correspondência exata: {len(found)}")
    if not found:
        found = images_from_listing_search(product)
        if found:
            source = "listing"
            print(f"Imagem resolvida via card da listagem pública do Mercado Livre: {len(found)}")
    if not found:
        page_url = str(product.get("canonical_url") or product.get("source_url") or "").strip()
        found = images_from_product_page(page_url)
        if found:
            source = "product_page"
            print(f"Imagens resolvidas via metadados da página: {len(found)}")
    combined = _dedupe(([existing_main] if existing_main else []) + existing_gallery + found)
    if not combined:
        print("Não foi possível resolver imagem real e confiável sem autenticação; mantendo campos vazios.")
        return False
    main = existing_main or combined[0]
    gallery = _dedupe([main] + combined)
    if source and source != "cache":
        _save_cache(cache, product, gallery, source, cache_path)
        print(f"Cache de imagens atualizado para {item_id}.")
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
