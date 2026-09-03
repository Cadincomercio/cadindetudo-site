from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "produtos"
TEMPLATE_PATH = ROOT / "templates" / "landing.html"
SITEMAP_PATH = ROOT / "sitemap.xml"
DEFAULT_SITE_URL = os.getenv("SITE_URL", "https://cadindetudo.com").rstrip("/")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152 Safari/537.36"
)


@dataclass
class Product:
    source_url: str
    title: str
    description: str
    image: str
    canonical_url: str
    slug_base: str
    item_id: str = ""


CLUSTER_PATTERNS = [
    ("motoboy", "para motoboy", "Manguito para motoboy"),
    ("moto", "para moto", "Manguito para moto"),
    ("dirigir-no-sol", "para dirigir no sol", "Manguito para dirigir no sol"),
    ("pesca", "para pesca", "Manguito para pesca"),
    ("ciclismo", "para ciclismo", "Manguito para ciclismo"),
    ("trabalho-rural", "para trabalho rural", "Manguito para trabalho rural"),
    ("jardinagem", "para jardinagem", "Manguito para jardinagem"),
    ("corrida", "para corrida", "Manguito para corrida"),
    ("com-polegar", "com polegar", "Manguito com polegar"),
    ("protecao-solar-uv50", "com proteção solar UV50+", "Manguito proteção solar UV50+"),
]


def slugify(value: str) -> str:
    value = value.lower().strip()
    replacements = {
        "á": "a", "à": "a", "â": "a", "ã": "a",
        "é": "e", "ê": "e", "í": "i", "ó": "o",
        "ô": "o", "õ": "o", "ú": "u", "ç": "c",
    }
    for src, dst in replacements.items():
        value = value.replace(src, dst)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "produto"


def request_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def request_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def extract_item_id(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("wid", "item_id"):
        values = query.get(key, [])
        if values:
            match = re.search(r"MLB\d+", values[0], flags=re.I)
            if match:
                return match.group(0).upper()

    match = re.search(r"MLB[-_]?([0-9]{6,})", url, flags=re.I)
    if match:
        return "MLB" + match.group(1)
    return ""


def title_from_url(url: str) -> str:
    path = urllib.parse.urlsplit(url).path.strip("/")
    first = path.split("/")[0] if path else ""
    first = urllib.parse.unquote(first)
    words = first.replace("-", " ").strip()
    if not words:
        return "Produto Mercado Livre"
    return " ".join(word.upper() if word.lower() in {"uv50", "npk"} else word.capitalize() for word in words.split())


def clean_destination_url(url: str, item_id: str = "") -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parsed.query)
    kept: list[tuple[str, str]] = []
    for key in ("pdp_filters", "wid"):
        for value in query.get(key, []):
            kept.append((key, value))
    if item_id and not any(k == "wid" for k, _ in kept):
        kept.append(("wid", item_id))
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(kept), ""))


def extract_meta(page: str, key: str) -> str:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+name=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(key)}["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(key)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, page, flags=re.I | re.S)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def extract_html_title(page: str) -> str:
    for key in ("og:title", "twitter:title"):
        value = extract_meta(page, key)
        if value:
            return value
    match = re.search(r"<title[^>]*>(.*?)</title>", page, flags=re.I | re.S)
    return html.unescape(re.sub(r"\s+", " ", match.group(1))).strip() if match else ""


def product_from_api(url: str, item_id: str) -> Product | None:
    if not item_id:
        return None
    try:
        data = request_json(f"https://api.mercadolibre.com/items/{item_id}")
    except Exception as exc:
        print(f"API Mercado Livre indisponível para {item_id}: {exc}", file=sys.stderr)
        return None

    title = str(data.get("title") or "").strip()
    if not title:
        return None

    pictures = data.get("pictures") or []
    image = ""
    if pictures and isinstance(pictures[0], dict):
        image = str(pictures[0].get("secure_url") or pictures[0].get("url") or "")

    permalink = str(data.get("permalink") or "").strip()
    attributes = []
    for attr in data.get("attributes") or []:
        if not isinstance(attr, dict):
            continue
        name = str(attr.get("name") or "").strip()
        value = str(attr.get("value_name") or "").strip()
        if name and value and value.lower() not in {"não informado", "nao informado", "n/a"}:
            attributes.append(f"{name}: {value}")
        if len(attributes) >= 5:
            break

    description = ". ".join(attributes)
    base = slugify(re.sub(r"\b(kit|par|pares|preto|cadin|uv50\+?)\b", " ", title, flags=re.I))
    return Product(
        source_url=url,
        title=title,
        description=description,
        image=image,
        canonical_url=permalink or clean_destination_url(url, item_id),
        slug_base=base[:70].rstrip("-"),
        item_id=item_id,
    )


def extract_product(url: str) -> Product:
    item_id = extract_item_id(url)
    api_product = product_from_api(url, item_id)
    if api_product:
        return api_product

    page = ""
    try:
        page = request_text(url)
    except Exception as exc:
        print(f"Página do anúncio não pôde ser lida: {exc}", file=sys.stderr)

    html_title = extract_html_title(page) if page else ""
    generic_titles = {"mercado libre", "mercado livre", "mercadolivre", "produto mercado livre"}
    title = html_title.strip()
    if not title or title.lower() in generic_titles:
        title = title_from_url(url)

    description = extract_meta(page, "description") or extract_meta(page, "og:description") if page else ""
    image = extract_meta(page, "og:image") or extract_meta(page, "twitter:image") if page else ""
    canonical = clean_destination_url(url, item_id)
    base = slugify(re.sub(r"\b(kit|par|pares|preto|cadin|uv50\+?)\b", " ", title, flags=re.I))

    return Product(
        source_url=url,
        title=title,
        description=description,
        image=image,
        canonical_url=canonical,
        slug_base=base[:70].rstrip("-"),
        item_id=item_id,
    )


def infer_clusters(product: Product, max_pages: int) -> list[dict]:
    title_l = product.title.lower()
    if "manguito" in title_l:
        return [
            {"slug": f"manguito-{slug}", "phrase": phrase, "heading": heading}
            for slug, phrase, heading in CLUSTER_PATTERNS[:max_pages]
        ]

    return [{
        "slug": product.slug_base,
        "phrase": "guia de compra",
        "heading": product.title,
    }]


def render_template(template: str, product: Product, cluster: dict) -> str:
    values = {
        "{{TITLE}}": html.escape(f"{cluster['heading']} | Cadin de Tudo"),
        "{{H1}}": html.escape(cluster["heading"]),
        "{{PRODUCT_TITLE}}": html.escape(product.title),
        "{{DESCRIPTION}}": html.escape(product.description or f"Informações práticas sobre {product.title}."),
        "{{IMAGE_URL}}": html.escape(product.image, quote=True),
        "{{ML_URL}}": html.escape(product.canonical_url, quote=True),
        "{{INTENT_PHRASE}}": html.escape(cluster["phrase"]),
    }
    rendered = template
    for needle, replacement in values.items():
        rendered = rendered.replace(needle, replacement)
    return rendered


def save_product(product: Product) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{product.slug_base}.json"
    path.write_text(json.dumps(asdict(product), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate_pages(product: Product, clusters: Iterable[dict]) -> list[str]:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    generated = []
    for cluster in clusters:
        slug = cluster["slug"]
        page_dir = ROOT / slug
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(render_template(template, product, cluster), encoding="utf-8")
        generated.append(slug)
    return generated


def build_sitemap(extra_slugs: Iterable[str]) -> None:
    urls = {DEFAULT_SITE_URL + "/"}
    for child in ROOT.iterdir():
        if child.is_dir() and (child / "index.html").exists() and not child.name.startswith("."):
            if child.name != "mercado-libre":
                urls.add(f"{DEFAULT_SITE_URL}/{child.name}/")
    for slug in extra_slugs:
        urls.add(f"{DEFAULT_SITE_URL}/{slug}/")

    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for page_url in sorted(urls):
        body.extend(["  <url>", f"    <loc>{html.escape(page_url)}</loc>", "  </url>"])
    body.append("</urlset>")
    SITEMAP_PATH.write_text("\n".join(body) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera páginas SEO a partir de uma URL do Mercado Livre")
    parser.add_argument("--url", required=True)
    parser.add_argument("--max-pages", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if "mercadolivre.com" not in args.url and "mercadolivre.com.br" not in args.url:
        print("A URL informada não parece ser do Mercado Livre.", file=sys.stderr)
        return 2

    max_pages = min(max(args.max_pages, 1), 12)
    product = extract_product(args.url)

    if product.title.lower() in {"mercado libre", "mercado livre"}:
        print("Não foi possível identificar o produto com segurança; nada foi publicado.", file=sys.stderr)
        return 3

    save_product(product)
    clusters = infer_clusters(product, max_pages=max_pages)
    slugs = generate_pages(product, clusters)
    build_sitemap(slugs)

    print(json.dumps({
        "produto": product.title,
        "item_id": product.item_id,
        "imagem": bool(product.image),
        "paginas": slugs,
        "total": len(slugs),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
