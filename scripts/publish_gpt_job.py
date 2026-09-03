from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "landing.html"
SITEMAP = ROOT / "sitemap.xml"
SITE_URL = os.getenv("SITE_URL", "https://cadindetudo.com").rstrip("/")

REQUIRED_CLUSTER_FIELDS = {
    "slug", "heading", "meta_description", "intro", "why", "observe", "faq_q", "faq_a"
}


def esc(value: object, quote: bool = False) -> str:
    return html.escape(str(value or ""), quote=quote)


def validate(job: dict) -> None:
    if not isinstance(job, dict):
        raise ValueError("Job precisa ser um objeto JSON")
    product = job.get("product")
    clusters = job.get("clusters")
    if not isinstance(product, dict):
        raise ValueError("Campo product ausente")
    for field in ("title", "ml_url"):
        if not str(product.get(field) or "").strip():
            raise ValueError(f"product.{field} é obrigatório")
    if not isinstance(clusters, list) or not clusters:
        raise ValueError("clusters precisa ter ao menos uma página")
    if len(clusters) > 20:
        raise ValueError("Máximo de 20 clusters por job")
    seen = set()
    for cluster in clusters:
        if not isinstance(cluster, dict):
            raise ValueError("Cluster inválido")
        missing = REQUIRED_CLUSTER_FIELDS - set(cluster)
        if missing:
            raise ValueError(f"Cluster sem campos: {sorted(missing)}")
        slug = str(cluster["slug"]).strip()
        if not slug or "/" in slug or ".." in slug:
            raise ValueError(f"Slug inválido: {slug}")
        if slug in seen:
            raise ValueError(f"Slug duplicado: {slug}")
        seen.add(slug)


def render(template: str, product: dict, cluster: dict) -> str:
    description = str(product.get("description") or "").strip()
    if not description:
        description = f"Oferta do produto {product['title']} no Mercado Livre."

    replacements = {
        "{{TITLE}}": esc(f"{cluster['heading']} | Cadin de Tudo"),
        "{{META_DESCRIPTION}}": esc(cluster["meta_description"]),
        "{{H1}}": esc(cluster["heading"]),
        "{{INTRO}}": esc(cluster["intro"]),
        "{{IMAGE_URL}}": esc(product.get("image_url", ""), quote=True),
        "{{PRODUCT_TITLE}}": esc(product["title"]),
        "{{ML_URL}}": esc(product["ml_url"], quote=True),
        "{{INTENT_PHRASE}}": esc(cluster.get("intent_phrase") or "para este uso"),
        "{{WHY}}": esc(cluster["why"]),
        "{{OBSERVE}}": esc(cluster["observe"]),
        "{{FAQ_Q}}": esc(cluster["faq_q"]),
        "{{FAQ_A}}": esc(cluster["faq_a"]),
        "{{PRODUCT_DESCRIPTION}}": esc(description),
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
    job = json.loads(job_path.read_text(encoding="utf-8"))
    validate(job)
    product = job["product"]
    template = TEMPLATE.read_text(encoding="utf-8")
    slugs = []
    for cluster in job["clusters"]:
        slug = cluster["slug"]
        target = ROOT / slug
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(render(template, product, cluster), encoding="utf-8")
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
