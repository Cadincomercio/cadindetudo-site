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


CLUSTERS = {
    "motoboy": {
        "slug": "manguito-para-motoboy",
        "phrase": "para motoboy",
        "heading": "Manguito para motoboy",
        "intro": "Para quem trabalha fazendo entregas de moto, braços e parte das mãos podem ficar expostos ao sol por muitas horas. Um manguito comprido, leve e com abertura para o polegar ajuda a manter cobertura durante a rotina sem limitar os dedos.",
        "why": "Na moto, a posição dos braços mantém a pele exposta por longos períodos. O modelo com polegar prolonga a cobertura sobre parte da mão e permite alternar entre pilotagem, celular e tarefas de entrega sem retirar a peça.",
        "observe": "Para uso diário, vale priorizar comprimento, mobilidade e facilidade de lavagem. Um kit com dois pares também permite alternar o uso enquanto um deles está sendo higienizado.",
        "faq_q": "Dois pares fazem sentido para quem usa todos os dias?",
        "faq_a": "Sim. Para uso frequente, dois pares facilitam a alternância entre uso e lavagem e deixam um segundo par disponível para a rotina.",
    },
    "moto": {
        "slug": "manguito-para-moto",
        "phrase": "para moto",
        "heading": "Manguito para moto",
        "intro": "Em trajetos de moto, o braço recebe exposição direta ao sol e ao vento. Um manguito leve pode ser uma alternativa prática para quem quer cobertura sem vestir uma segunda camada pesada.",
        "why": "Ao pilotar, braços e punhos permanecem em posição fixa e exposta. A abertura para o polegar ajuda a manter a peça no lugar e estende a cobertura sobre parte da mão.",
        "observe": "Confira se o tecido permite movimentos livres no guidão, se o comprimento cobre bem o braço e se o ajuste não incomoda durante trajetos mais longos.",
        "faq_q": "O manguito atrapalha o uso das mãos na moto?",
        "faq_a": "O modelo com polegar mantém os dedos livres, então acelerador, freio e comandos continuam acessíveis. O ajuste deve ser confortável e sem excesso de compressão.",
    },
    "dirigir-no-sol": {
        "slug": "manguito-para-dirigir-no-sol",
        "phrase": "para dirigir no sol",
        "heading": "Manguito para dirigir no sol",
        "intro": "Quem dirige por muito tempo costuma perceber maior exposição no braço próximo à janela. Um manguito comprido ajuda a criar cobertura adicional durante viagens, deslocamentos e trabalho ao volante.",
        "why": "A luz que entra pela lateral do veículo atinge principalmente braço e mão próximos à janela. O formato com polegar amplia a cobertura sem impedir o uso do volante e dos comandos.",
        "observe": "Para dirigir, conforto térmico, flexibilidade e cobertura da mão são pontos importantes. Prefira uma peça que possa ser colocada e retirada rapidamente.",
        "faq_q": "Serve para quem dirige várias horas por dia?",
        "faq_a": "Pode ser uma opção prática para motoristas e pessoas que passam longos períodos ao volante, principalmente quando buscam cobertura leve e fácil de remover.",
    },
    "pesca": {
        "slug": "manguito-para-pesca",
        "phrase": "para pesca",
        "heading": "Manguito para pesca",
        "intro": "Na pesca, braços e mãos ficam expostos por períodos prolongados, muitas vezes com reflexo da luz sobre a água. Um manguito comprido ajuda a manter cobertura sem comprometer o manuseio de vara, linha e equipamentos.",
        "why": "O polegar mantém o manguito posicionado enquanto os dedos continuam livres para nós, anzóis, carretilhas e outros movimentos finos comuns na pescaria.",
        "observe": "Além da cobertura, considere secagem, mobilidade e conforto ao longo de várias horas. O tecido deve acompanhar os movimentos sem enrolar com facilidade.",
        "faq_q": "O modelo com polegar é útil para pescador?",
        "faq_a": "Sim, porque cobre parte da mão e deixa os dedos livres, combinação útil para atividades que exigem precisão no manuseio de equipamentos.",
    },
    "ciclismo": {
        "slug": "manguito-para-ciclismo",
        "phrase": "para ciclismo",
        "heading": "Manguito para ciclismo",
        "intro": "No ciclismo, os braços ficam expostos durante todo o percurso. Um manguito leve e flexível pode oferecer cobertura adicional sem exigir uma camisa de manga longa.",
        "why": "A posição no guidão deixa braços e punhos continuamente expostos. O encaixe para o polegar ajuda a manter a peça estendida durante o movimento.",
        "observe": "Mobilidade, ajuste e conforto são essenciais. A peça não deve limitar o movimento dos punhos nem criar excesso de tecido próximo às mãos.",
        "faq_q": "É uma opção para pedal longo?",
        "faq_a": "Para quem busca uma camada leve e removível durante o pedal, o manguito pode ser prático, desde que o ajuste permaneça confortável ao longo do percurso.",
    },
    "trabalho-rural": {
        "slug": "manguito-para-trabalho-rural",
        "phrase": "para trabalho rural",
        "heading": "Manguito para trabalho rural",
        "intro": "Atividades rurais frequentemente exigem longos períodos ao ar livre. Um manguito comprido pode ser uma camada prática para quem precisa de cobertura dos braços sem usar roupa pesada.",
        "why": "No campo, a peça pode ser colocada e retirada conforme a atividade e ajuda a cobrir braço e parte da mão durante tarefas externas.",
        "observe": "Dê preferência a tecido flexível, facilidade de lavagem e comprimento adequado. Em trabalho intenso, conforto e mobilidade são mais importantes do que compressão forte.",
        "faq_q": "Pode ser usado durante tarefas no campo?",
        "faq_a": "Pode ser usado como peça de cobertura em atividades externas, desde que não seja tratado como substituto de EPI quando a tarefa exigir equipamento de proteção regulamentado.",
    },
    "jardinagem": {
        "slug": "manguito-para-jardinagem",
        "phrase": "para jardinagem",
        "heading": "Manguito para jardinagem",
        "intro": "Podas, regas e manutenção do jardim podem manter os braços expostos ao sol por bastante tempo. Um manguito leve oferece cobertura adicional e pode ser retirado assim que a atividade termina.",
        "why": "A cobertura até parte da mão ajuda em tarefas externas, enquanto os dedos livres facilitam o uso de tesouras, mangueiras e ferramentas pequenas.",
        "observe": "Considere flexibilidade, facilidade de lavagem e conforto ao movimentar punhos e cotovelos durante o trabalho.",
        "faq_q": "Manguito é prático para jardinagem?",
        "faq_a": "Para tarefas externas leves, pode ser uma opção prática de cobertura dos braços. Em atividades com riscos mecânicos ou químicos, devem ser usados os EPIs adequados.",
    },
    "corrida": {
        "slug": "manguito-para-corrida",
        "phrase": "para corrida",
        "heading": "Manguito para corrida",
        "intro": "Em corridas ao ar livre, o manguito permite acrescentar cobertura aos braços sem trocar a camiseta por uma peça de manga longa.",
        "why": "O tecido flexível acompanha o movimento dos braços, e o encaixe no polegar ajuda a evitar que a extremidade suba durante a atividade.",
        "observe": "Para corrida, vale observar ajuste, leveza e conforto com suor. A peça não deve restringir o balanço natural dos braços.",
        "faq_q": "Dá para usar com camiseta de manga curta?",
        "faq_a": "Sim. Esse é um dos usos mais comuns do formato: adicionar cobertura aos braços mantendo a camiseta de manga curta.",
    },
    "com-polegar": {
        "slug": "manguito-com-polegar",
        "phrase": "com polegar",
        "heading": "Manguito com polegar",
        "intro": "O diferencial do modelo com abertura para o polegar é estender a cobertura além do punho, alcançando parte da mão sem cobrir os dedos.",
        "why": "O polegar ajuda a manter a extremidade do manguito posicionada e reduz a tendência de a peça subir em atividades com movimento frequente dos braços.",
        "observe": "Verifique se a abertura fica confortável, se não aperta a base do polegar e se o tecido permite movimentar totalmente a mão.",
        "faq_q": "Qual a diferença para um manguito sem polegar?",
        "faq_a": "No modelo comum, a peça normalmente termina no punho. No modelo com polegar, há uma extensão que cobre parte da mão mantendo os dedos livres.",
    },
    "protecao-solar-uv50": {
        "slug": "manguito-protecao-solar-uv50",
        "phrase": "com proteção solar UV50+",
        "heading": "Manguito proteção solar UV50+",
        "intro": "Para atividades ao ar livre, um manguito UV50+ combina cobertura dos braços com a praticidade de uma peça removível e fácil de transportar.",
        "why": "O formato longo cria cobertura do braço e, neste modelo, também de parte da mão. Isso o torna versátil para diferentes rotinas externas.",
        "observe": "Confirme a indicação UV do produto, o comprimento e o ajuste. A proteção da peça não elimina outras medidas de proteção solar recomendadas para a atividade.",
        "faq_q": "UV50+ significa que posso dispensar outras formas de proteção?",
        "faq_a": "Não. O manguito é uma camada de cobertura para a área vestida. Outras áreas expostas continuam exigindo os cuidados adequados ao contexto de uso.",
    },
}


def slugify(value: str) -> str:
    value = value.lower().strip()
    replacements = {"á":"a","à":"a","â":"a","ã":"a","é":"e","ê":"e","í":"i","ó":"o","ô":"o","õ":"o","ú":"u","ç":"c"}
    for src, dst in replacements.items():
        value = value.replace(src, dst)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "produto"


def request_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent":USER_AGENT,"Accept-Language":"pt-BR,pt;q=0.9,en;q=0.7","Accept":"text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=25) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def request_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent":USER_AGENT,"Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def extract_item_id(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("wid", "item_id"):
        for value in query.get(key, []):
            match = re.search(r"MLB\d+", value, flags=re.I)
            if match:
                return match.group(0).upper()
    match = re.search(r"MLB[-_]?([0-9]{6,})", url, flags=re.I)
    return "MLB" + match.group(1) if match else ""


def title_from_url(url: str) -> str:
    path = urllib.parse.urlsplit(url).path.strip("/")
    first = urllib.parse.unquote(path.split("/")[0] if path else "")
    words = first.replace("-", " ").strip()
    return " ".join(word.upper() if word.lower() in {"uv50", "npk"} else word.capitalize() for word in words.split()) or "Produto Mercado Livre"


def clean_destination_url(url: str, item_id: str = "") -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parsed.query)
    kept = []
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
    image = ""
    pictures = data.get("pictures") or []
    if pictures and isinstance(pictures[0], dict):
        image = str(pictures[0].get("secure_url") or pictures[0].get("url") or "")
    if not image:
        thumb = str(data.get("secure_thumbnail") or data.get("thumbnail") or "")
        image = thumb.replace("-I.jpg", "-O.jpg").replace("-I.webp", "-O.webp") if thumb else ""
    permalink = str(data.get("permalink") or "").strip()
    attributes = []
    for attr in data.get("attributes") or []:
        if not isinstance(attr, dict):
            continue
        name, value = str(attr.get("name") or "").strip(), str(attr.get("value_name") or "").strip()
        if name and value and value.lower() not in {"não informado", "nao informado", "n/a"}:
            attributes.append(f"{name}: {value}")
        if len(attributes) >= 6:
            break
    description = ". ".join(attributes)
    base = slugify(re.sub(r"\b(kit|par|pares|preto|cadin|uv50\+?)\b", " ", title, flags=re.I))
    return Product(url, title, description, image, permalink or clean_destination_url(url, item_id), base[:70].rstrip("-"), item_id)


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
    title = extract_html_title(page).strip() if page else ""
    if not title or title.lower() in {"mercado libre","mercado livre","mercadolivre","produto mercado livre"}:
        title = title_from_url(url)
    description = (extract_meta(page, "description") or extract_meta(page, "og:description")) if page else ""
    image = (extract_meta(page, "og:image") or extract_meta(page, "twitter:image")) if page else ""
    base = slugify(re.sub(r"\b(kit|par|pares|preto|cadin|uv50\+?)\b", " ", title, flags=re.I))
    return Product(url, title, description, image, clean_destination_url(url, item_id), base[:70].rstrip("-"), item_id)


def infer_clusters(product: Product, max_pages: int) -> list[dict]:
    if "manguito" in product.title.lower():
        ordered = ["motoboy","moto","dirigir-no-sol","pesca","ciclismo","trabalho-rural","jardinagem","corrida","com-polegar","protecao-solar-uv50"]
        return [dict(CLUSTERS[key]) for key in ordered[:max_pages]]
    generic = {
        "slug": product.slug_base,
        "phrase": "para esta aplicação",
        "heading": product.title,
        "intro": f"Este guia reúne informações práticas para avaliar {product.title} antes da compra.",
        "why": "A escolha deve considerar a aplicação real, as dimensões, o material e as características informadas no anúncio.",
        "observe": "Compare as especificações do produto com a sua necessidade e confirme as condições da oferta antes da compra.",
        "faq_q": "O que conferir antes de comprar?",
        "faq_a": "Confira características, quantidade, medidas, material, compatibilidade e prazo de entrega conforme a sua necessidade.",
    }
    return [generic]


def render_template(template: str, product: Product, cluster: dict) -> str:
    meta_description = (cluster["intro"][:155].rstrip(" ,.;") + ".") if len(cluster["intro"]) > 155 else cluster["intro"]
    values = {
        "{{TITLE}}": html.escape(f"{cluster['heading']} | Cadin de Tudo"),
        "{{META_DESCRIPTION}}": html.escape(meta_description),
        "{{H1}}": html.escape(cluster["heading"]),
        "{{PRODUCT_TITLE}}": html.escape(product.title),
        "{{PRODUCT_DESCRIPTION}}": html.escape(product.description or f"Oferta do produto {product.title} no Mercado Livre."),
        "{{IMAGE_URL}}": html.escape(product.image, quote=True),
        "{{ML_URL}}": html.escape(product.canonical_url, quote=True),
        "{{INTENT_PHRASE}}": html.escape(cluster["phrase"]),
        "{{INTRO}}": html.escape(cluster["intro"]),
        "{{WHY}}": html.escape(cluster["why"]),
        "{{OBSERVE}}": html.escape(cluster["observe"]),
        "{{FAQ_Q}}": html.escape(cluster["faq_q"]),
        "{{FAQ_A}}": html.escape(cluster["faq_a"]),
    }
    rendered = template
    for needle, replacement in values.items():
        rendered = rendered.replace(needle, replacement)
    return rendered


def save_product(product: Product) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / f"{product.slug_base}.json").write_text(json.dumps(asdict(product), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


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


def remove_legacy_duplicate(generated_slugs: Iterable[str]) -> None:
    # Primeira página manual tinha slug diferente. Mantemos somente a URL canônica gerada pela máquina.
    if "manguito-para-motoboy" in set(generated_slugs):
        legacy = ROOT / "manguito-motoboy"
        if legacy.is_dir() and (legacy / "index.html").exists():
            (legacy / "index.html").unlink()
            try:
                legacy.rmdir()
            except OSError:
                pass


def build_sitemap(extra_slugs: Iterable[str]) -> None:
    urls = {DEFAULT_SITE_URL + "/"}
    excluded = {"mercado-libre", "manguito-motoboy"}
    for child in ROOT.iterdir():
        if child.is_dir() and (child / "index.html").exists() and not child.name.startswith(".") and child.name not in excluded:
            urls.add(f"{DEFAULT_SITE_URL}/{child.name}/")
    for slug in extra_slugs:
        urls.add(f"{DEFAULT_SITE_URL}/{slug}/")
    body = ['<?xml version="1.0" encoding="UTF-8"?>','<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page_url in sorted(urls):
        body.extend(["  <url>", f"    <loc>{html.escape(page_url)}</loc>", "  </url>"])
    body.append("</urlset>")
    SITEMAP_PATH.write_text("\n".join(body)+"\n", encoding="utf-8")


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
    remove_legacy_duplicate(slugs)
    build_sitemap(slugs)
    print(json.dumps({"produto":product.title,"item_id":product.item_id,"imagem":bool(product.image),"paginas":slugs,"total":len(slugs)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
