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
    "slug", "heading", "meta_description", "intro", "why", "observe",
    "faq_q", "faq_a", "search_intent", "candidate_terms"
}


def esc(value: object, quote: bool = False) -> str:
    return html.escape(str(value or ""), quote=quote)


def normalize(job: dict) -> dict:
    if not isinstance(job, dict):
        raise ValueError("Job precisa ser um objeto JSON")

    product = dict(job.get("product") or {})
    provided_images = product.get("provided_image_urls") or []
    if isinstance(provided_images, list) and provided_images:
        # URLs fornecidas pelo usuário são a fonte de verdade, na ordem recebida.
        product["main_image_url"] = provided_images[0]
        product["image_url"] = provided_images[0]
        product["gallery_images"] = provided_images
    if not product.get("canonical_url") and product.get("ml_url"):
        product["canonical_url"] = product["ml_url"]
    if not product.get("source_url"):
        product["source_url"] = product.get("canonical_url") or product.get("ml_url") or ""
    if not product.get("main_image_url") and product.get("image_url"):
        product["main_image_url"] = product["image_url"]
    if not product.get("image_url") and product.get("main_image_url"):
        product["image_url"] = product["main_image_url"]

    pages = job.get("pages")
    if pages is None:
        pages = job.get("clusters")

    return {
        "version": int(job.get("version") or 1),
        "publish": bool(job.get("publish", True)),
        "product_key": job.get("product_key") or "",
        "product": product,
        "research": job.get("research"),
        "pages": pages,
    }


def validate_string_list(value: object, field_name: str, max_items: int = 8, min_items: int = 0) -> None:
    if value is None:
        if min_items:
            raise ValueError(f"{field_name} é obrigatório")
        return
    if not isinstance(value, list):
        raise ValueError(f"{field_name} precisa ser uma lista")
    if len(value) < min_items:
        raise ValueError(f"{field_name} precisa ter ao menos {min_items} itens")
    if len(value) > max_items:
        raise ValueError(f"{field_name} excede o máximo de {max_items} itens")
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} contém item inválido")


def validate(job: dict) -> None:
    product = job["product"]
    research = job["research"]
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
    validate_string_list(product.get("provided_image_urls"), "product.provided_image_urls", max_items=8)
    validate_string_list(product.get("gallery_images"), "product.gallery_images", max_items=8)

    if not isinstance(research, dict):
        raise ValueError("research é obrigatório antes da publicação")
    validate_string_list(research.get("queries"), "research.queries", max_items=30, min_items=2)
    validate_string_list(research.get("candidate_terms"), "research.candidate_terms", max_items=80, min_items=4)
    if len(str(research.get("notes") or "").strip()) < 30:
        raise ValueError("research.notes precisa resumir a pesquisa realizada")

    if not isinstance(pages, list) or not pages:
        raise ValueError("pages precisa ter ao menos uma página")
    if len(pages) > 20:
        raise ValueError("Máximo de 20 páginas por job")

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

        if len(str(page.get("search_intent") or "").strip()) < 10:
            raise ValueError(f"search_intent insuficiente em {slug}")
        validate_string_list(page.get("candidate_terms"), f"pages[{slug}].candidate_terms", max_items=20, min_items=1)
        validate_string_list(page.get("highlights"), f"pages[{slug}].highlights")
        validate_string_list(page.get("checklist"), f"pages[{slug}].checklist")
        validate_string_list(page.get("benefit_cards"), f"pages[{slug}].benefit_cards", max_items=5)
        practical_note = page.get("practical_note")
        if practical_note is not None and not 20 <= len(str(practical_note).strip()) <= 360:
            raise ValueError(f"practical_note fora do limite em {slug}")

        blocks = page.get("practical_blocks")
        if blocks is not None:
            if not isinstance(blocks, list) or len(blocks) > 4:
                raise ValueError(f"practical_blocks inválido em {slug}")
            for block in blocks:
                if not isinstance(block, dict):
                    raise ValueError(f"practical_blocks inválido em {slug}")
                if not str(block.get("title") or "").strip() or not str(block.get("body") or "").strip():
                    raise ValueError(f"practical_blocks incompleto em {slug}")

        faqs = page.get("faqs")
        if faqs is not None:
            if not isinstance(faqs, list) or len(faqs) > 4:
                raise ValueError(f"faqs inválido em {slug}")
            for faq in faqs:
                if not isinstance(faq, dict):
                    raise ValueError(f"faqs inválido em {slug}")
                if not str(faq.get("question") or "").strip() or not str(faq.get("answer") or "").strip():
                    raise ValueError(f"faqs incompleto em {slug}")


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


def benefits_html(items: list[str]) -> str:
    return list_html(items[:5], "benefits")


def gallery_html(product: dict, page: dict) -> str:
    gallery = product.get("gallery_images") or []
    if not isinstance(gallery, list):
        gallery = []
    images, seen = [], set()
    for value in gallery:
        image = str(value or "").strip()
        if image and image not in seen:
            images.append(image)
            seen.add(image)

    main = _main_image(product)
    if not images and main:
        images = [main]
    if not images:
        return '<div class="gallery"><div class="visual-theme">' + esc(product.get("title") or "Produto selecionado") + '</div></div>'

    title = str(product.get("title") or "Produto").strip()
    context_image = images[1] if len(images) > 1 else str(page.get("context_image_url") or "").strip()
    if context_image == images[0]:
        context_image = ""
    thumbs = []
    for index, image in enumerate(images):
        alt = f"{title} — imagem {index + 1}"
        current = "true" if index == 0 else "false"
        thumbs.append(
            f'<button class="thumb" type="button" data-gallery-thumb data-src="{esc(image, quote=True)}" '
            f'data-alt="{esc(alt, quote=True)}" aria-label="Ver imagem {index + 1}" aria-current="{current}">'
            f'<img loading="lazy" src="{esc(image, quote=True)}" alt=""></button>'
        )
    main_alt = f"{title} — imagem 1"
    context = ""
    if context_image:
        context = (
            f'<img class="context-background" src="{esc(context_image, quote=True)}" alt="" '
            'aria-hidden="true" onerror="this.style.display=\'none\'">'
        )
    thumbs_html = ""
    if len(images) > 1:
        thumbs_html = '<div class="thumbs" aria-label="Galeria do produto">' + "".join(thumbs) + '</div>'
    return (
        '<div class="gallery"><div class="visual-stage">' + context +
        '<div class="visual-overlay"></div><div class="main-photo">'
        f'<img data-gallery-main fetchpriority="high" src="{esc(images[0], quote=True)}" alt="{esc(main_alt, quote=True)}">'
        '</div></div>' + thumbs_html + '</div>'
    )


def benefit_section_html(items: list[str]) -> str:
    if not items:
        return ""
    cards = "".join(f'<div class="benefit">{esc(item)}</div>' for item in items)
    return '<section class="section"><h2>Principais pontos para sua decisão</h2><div class="benefits">' + cards + '</div><div class="cta-row"><a class="cta cta-primary" data-cadin-cta="mercado-livre" href="{{ML_URL}}" target="_blank" rel="noopener">{{CTA_PRIMARY}}</a></div></section>'


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
    return '<section class="section"><h2>Orientações práticas</h2><div class="practical-grid">' + "".join(inner) + '</div><div class="cta-row"><a class="cta cta-secondary" data-cadin-cta="mercado-livre" href="{{ML_URL}}" target="_blank" rel="noopener">{{CTA_SECONDARY}}</a></div></section>'


def faqs_html(page: dict) -> str:
    faqs = page.get("faqs") or []
    if not faqs:
        faqs = [{"question": page.get("faq_q"), "answer": page.get("faq_a")}]
    parts = []
    for faq in faqs:
        parts.append(
            '<div class="faq-item">'
            f'<h3>{esc(faq.get("question"))}</h3>'
            f'<p>{esc(faq.get("answer"))}</p>'
            '</div>'
        )
    return "".join(parts)


def _main_image(product: dict) -> str:
    return str(product.get("main_image_url") or product.get("image_url") or "").strip()


def hero_visual_html(product: dict, page: dict) -> str:
    image = _main_image(product)
    if image:
        return (
            f'<img class="product-image" src="{esc(image, quote=True)}" '
            f'alt="{esc(product.get("title"), quote=True)}" onerror="this.style.display=\'none\'">'
        )
    theme = str(page.get("image_theme") or page.get("search_intent") or product.get("title") or "").strip()
    return '<div class="visual-theme"><div class="icon">🌿</div><strong>Contexto de uso</strong><span>' + esc(theme) + '</span></div>'


def offer_visual_html(product: dict) -> str:
    image = _main_image(product)
    if not image:
        return ""
    return (
        '<div class="offer-photo"><img class="product-image" loading="lazy" '
        f'src="{esc(image, quote=True)}" alt="{esc(product.get("title"), quote=True)}" '
        'onerror="this.closest(\'.offer-photo\').style.display=\'none\'"></div>'
    )


def context_visual_html(page: dict) -> str:
    image = str(page.get("context_image_url") or "").strip()
    theme = str(page.get("image_theme") or "").strip()
    if image:
        return '<section class="section"><h2>Visualize esta aplicação</h2><img class="context-image" src="' + esc(image, quote=True) + '" alt="' + esc(theme or "Aplicação do produto", quote=True) + '" onerror="this.closest(\'section\').style.display=\'none\'"></section>'
    if theme:
        return '<section class="section"><h2>Onde esta solução se encaixa</h2><div class="visual-theme"><div class="icon">🔎</div><strong>Aplicação pesquisada</strong><span>' + esc(theme) + '</span></div></section>'
    return ""


def render(template: str, product: dict, page: dict) -> str:
    description = str(product.get("description") or "").strip()
    if not description:
        description = f"Oferta do produto {product['title']} no Mercado Livre."

    highlights = page.get("highlights")
    if highlights is None:
        highlights = product.get("highlights") or []

    benefit_cards = page.get("benefit_cards") or highlights or []
    hero_subtitle = str(page.get("hero_subtitle") or page.get("search_intent") or page.get("intro") or "").strip()
    closing_text = str(page.get("closing_text") or description).strip()
    cta_primary = str(page.get("cta_primary_label") or "COMPRAR AGORA NO MERCADO LIVRE").strip()
    cta_secondary = str(page.get("cta_secondary_label") or "VER PREÇO E ENTREGA").strip()

    replacements = {
        "{{TITLE}}": esc(f"{page['heading']} | Cadin de Tudo"),
        "{{META_DESCRIPTION}}": esc(page["meta_description"]),
        "{{H1}}": esc(page["heading"]),
        "{{INTRO}}": esc(page["intro"]),
        "{{HERO_SUBTITLE}}": esc(hero_subtitle),
        "{{HERO_VISUAL_HTML}}": hero_visual_html(product, page),
        "{{GALLERY_HTML}}": gallery_html(product, page),
        "{{OFFER_VISUAL_HTML}}": offer_visual_html(product),
        "{{HIGHLIGHTS_HTML}}": highlights_html(highlights),
        "{{BENEFIT_SECTION_HTML}}": benefit_section_html(benefit_cards),
        "{{BENEFITS_HTML}}": benefits_html(benefit_cards),
        "{{PRODUCT_TITLE}}": esc(product["title"]),
        "{{ML_URL}}": esc(product["canonical_url"], quote=True),
        "{{WHY}}": esc(page["why"]),
        "{{OBSERVE}}": esc(page["observe"]),
        "{{PRACTICAL_NOTE}}": esc(page.get("practical_note") or page["observe"]),
        "{{CHECKLIST_HTML}}": list_html(page.get("checklist") or []),
        "{{CONTEXT_VISUAL_HTML}}": context_visual_html(page),
        "{{PRACTICAL_BLOCKS_HTML}}": practical_blocks_html(page.get("practical_blocks") or []),
        "{{FAQS_HTML}}": faqs_html(page),
        "{{PRODUCT_DESCRIPTION}}": esc(description),
        "{{CLOSING_TEXT}}": esc(closing_text),
        "{{CTA_PRIMARY}}": esc(cta_primary),
        "{{CTA_SECONDARY}}": esc(cta_secondary),
        "{{TRACK_PRODUCT}}": esc(product.get("item_id") or product["title"], quote=True),
        "{{TRACK_PAGE}}": esc(page["slug"], quote=True),
        "{{TRACK_DESTINATION}}": esc(product["canonical_url"], quote=True),
    }
    output = template
    for _ in range(2):
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
