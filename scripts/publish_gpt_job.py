from __future__ import annotations

import argparse
import html
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "landing.html"
SITEMAP = ROOT / "sitemap.xml"
SITE_URL = os.getenv("SITE_URL", "https://cadindetudo.com").rstrip("/")

REQUIRED_PAGE_FIELDS = {
    "slug", "heading", "meta_description", "intro", "why", "observe", "faq_q", "faq_a"
}


def esc(value: object, quote: bool = False) -> str:
    return html.escape(str(value or ""), quote=quote)


def normalize(job: dict) -> dict:
    if not isinstance(job, dict):
        raise ValueError("Job precisa ser um objeto JSON")

    product = dict(job.get("product") or {})
    if not product.get("canonical_url") and product.get("ml_url"):
        product["canonical_url"] = product["ml_url"]
    if not product.get("source_url"):
        product["source_url"] = product.get("canonical_url") or product.get("ml_url") or ""

    pages = job.get("pages")
    if pages is None:
        pages = job.get("clusters")

    return {
        "version": int(job.get("version") or 1),
        "publish": bool(job.get("publish", True)),
        "product_key": job.get("product_key") or "",
        "product": product,
        "pages": pages,
    }


def validate_string_list(value: object, field_name: str, max_items: int = 8) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        raise ValueError(f"{field_name} precisa ser uma lista")
    if len(value) > max_items:
        raise ValueError(f"{field_name} excede o máximo de {max_items} itens")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} contém item inválido")


def validate(job: dict) -> None:
    product = job["product"]
    pages = job["pages"]

    if job["version"] != 1:
        raise ValueError("Versão de job não suportada")
    if not isinstance(product, dict):
        raise ValueError("Campo product ausente")

    for field in ("title", "canonical_url"):
        if not str(product.get(field) or "").strip():
            raise ValueError(f"product.{field} é obrigatório")

    canonical = str(product.get("canonical_url") or "")
    if "mercadolivre.com" not in canonical and "mercadolivre.com.br" not in canonical:
        raise ValueError("product.canonical_url precisa apontar para Mercado Livre")

    validate_string_list(product.get("highlights"), "product.highlights")

    if not isinstance(pages, list) or not pages:
        raise ValueError("pages precisa ter ao menos uma página")
    if len(pages) > 12:
        raise ValueError("Máximo de 12 páginas por job")

    seen = set()
    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("Página inválida")
        missing = REQUIRED_PAGE_FIELDS - set(page)
        if missing:
            raise ValueError(f"Página sem campos: {sorted(missing)}")

        slug = str(page["slug"]).strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError(f"Slug inválido: {slug}")
        if slug in seen:
            raise ValueError(f"Slug duplicado: {slug}")
        seen.add(slug)

        meta = str(page["meta_description"]).strip()
        if len(meta) < 30 or len(meta) > 180:
            raise ValueError(f"meta_description fora do limite em {slug}")

        validate_string_list(page.get("highlights"), f"pages[{slug}].highlights")
        validate_string_list(page.get("checklist"), f"pages[{slug}].checklist")

        blocks = page.get("practical_blocks")
        if blocks is not None:
            if not isinstance(blocks, list) or len(blocks) > 4:
                raise ValueError(f"practical_blocks inválido em {slug}")
            for block in blocks:
                if not isinstance(block, dict):
                    raise ValueError(f"practical_blocks inválido em {slug}")
                if not str(block.get("title") or "").strip() or not str(block.get("body") or "").strip():
                    raise ValueError(f"practical_blocks incompleto em {slug}")


def list_html(items: list[str], css_class: str = "facts") -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{esc(item)}</li>" for item in items)
    return f'<ul class="{css_class}">{lis}</ul>'


def highlights_html(items: list[str]) -> str:
    if not items:
        return ""
    chips = "".join(f'<div class="chip">{esc(item)}</div>' for item in items)
    return f'<div class="chips">{chips}</div>'


def practical_blocks_html(blocks: list[dict]) -> str:
    if not blocks:
        return ""
    inner = []
    for block in blocks:
        inner.append(
            '<div class="practical-block">'
            f'<h3>{esc(block.get("title"))}</h3>'
            f'<p>{esc(block.get("body"))}</p>'
            '</div>'
        )
    return '<section class="card"><h2>Informações práticas</h2>' + "".join(inner) + '</section>'


def image_html(product: dict) -> str:
    image = str(product.get("image_url") or "").strip()
    if not image:
        return ""
    return (
        f'<img class="product-image" src="{esc(image, quote=True)}" '
        f'alt="{esc(product.get("title"), quote=True)}" onerror="this.style.display=\'none\'">'
    )


def render(template: str, product: dict, page: dict) -> str:
    description = str(product.get("description") or "").strip()
    if not description:
        description = f"Oferta do produto {product['title']} no Mercado Livre."

    highlights = page.get("highlights")
    if highlights is None:
        highlights = product.get("highlights") or []

    replacements = {
        "{{TITLE}}": esc(f"{page['heading']} | Cadin de Tudo"),
        "{{META_DESCRIPTION}}": esc(page["meta_description"]),
        "{{H1}}": esc(page["heading"]),
        "{{INTRO}}": esc(page["intro"]),
        "{{IMAGE_HTML}}": image_html(product),
        "{{HIGHLIGHTS_HTML}}": highlights_html(highlights),
        "{{PRODUCT_TITLE}}": esc(product["title"]),
        "{{ML_URL}}": esc(product["canonical_url"], quote=True),
        "{{WHY}}": esc(page["why"]),
        "{{OBSERVE}}": esc(page["observe"]),
        "{{CHECKLIST_HTML}}": list_html(page.get("checklist") or []),
        "{{PRACTICAL_BLOCKS_HTML}}": practical_blocks_html(page.get("practical_blocks") or []),
        "{{FAQ_Q}}": esc(page["faq_q"]),
        "{{FAQ_A}}": esc(page["faq_a"]),
        "{{PRODUCT_DESCRIPTION}}": esc(description),
        "{{TRACK_PRODUCT}}": esc(product.get("item_id") or product["title"], quote=True),
        "{{TRACK_PAGE}}": esc(page["slug"], quote=True),
        "{{TRACK_DESTINATION}}": esc(product["canonical_url"], quote=True),
    }
    output = template
    for needle, value in replacements.items():
        output = output.replace(needle, value)
    return output


def build_sitemap() -> None:
    urls = {SITE_URL + "/"}
    for child in ROOT.iterdir():
        if child.is_dir() and not child.name.startswith(".") and (child / "index.html").exists():
            urls.add(f"{SITE_URL}/{child.name}/")

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in sorted(urls):
        lines.extend(["  <url>", f"    <loc>{html.escape(url)}</loc>", "  </url>"])
    lines.append("</urlset>")
    SITEMAP.write_text("\n".join(lines) + "\n", encoding="utf-8")


def publish(job_path: Path) -> list[str]:
    raw_job = json.loads(job_path.read_text(encoding="utf-8"))
    job = normalize(raw_job)
    validate(job)

    if not job["publish"]:
        print("Job validado com publish=false; nenhuma página será gravada.")
        return []

    product = job["product"]
    template = TEMPLATE.read_text(encoding="utf-8")
    slugs = []

    for page in job["pages"]:
        slug = page["slug"]
        target = ROOT / slug
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(render(template, product, page), encoding="utf-8")
        slugs.append(slug)

    product_key = str(job.get("product_key") or product["title"]).lower().replace(" ", "-")[:80]
    safe_key = "".join(ch for ch in product_key if ch.isalnum() or ch in "-_").strip("-") or "produto"
    data_path = ROOT / "data" / "produtos" / f"{safe_key}.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(product, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    build_sitemap()
    return slugs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    args = parser.parse_args()

    path = Path(args.job)
    if not path.is_absolute():
        path = ROOT / path

    slugs = publish(path)
    print(json.dumps({"published": slugs, "total": len(slugs)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
