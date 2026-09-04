# Cadin SEO Engine — Automação v1

## Objetivo

Receber uma URL de anúncio do Mercado Livre e gerar páginas SEO estáticas dentro deste repositório. Cada commit no branch `main` é publicado automaticamente pelo Cloudflare Pages.

## Fluxo operacional

1. Abrir **Actions** no GitHub.
2. Selecionar **Gerar paginas SEO**.
3. Clicar em **Run workflow**.
4. Colar a URL do anúncio do Mercado Livre.
5. Definir a quantidade máxima de páginas (1 a 20).
6. Manter `publish = true`.
7. Executar.

O workflow:

- lê a URL do Mercado Livre;
- tenta obter título, descrição, imagem e URL canônica;
- salva os dados estruturados em `data/produtos/`;
- cria clusters iniciais;
- gera páginas usando `templates/landing.html`;
- atualiza `sitemap.xml`;
- faz commit e push automaticamente;
- o Cloudflare Pages detecta o commit e publica o site.

## Arquitetura

```text
.github/workflows/gerar-seo.yml   # botão da automação
scripts/generate_seo.py           # motor atual
templates/landing.html            # template central
data/produtos/                    # cadastro estruturado dos produtos
sitemap.xml                       # URLs publicáveis
```

## Estado da v1

A v1 é propositalmente conservadora:

- para `manguito`, usa até 10 clusters pré-definidos e distintos;
- para produtos ainda não modelados, gera somente uma página genérica, evitando criar dezenas de páginas artificiais;
- não depende de API paga;
- mantém as páginas geradas como `noindex,nofollow` enquanto o domínio definitivo e a qualidade editorial ainda estiverem em validação.

## Próxima camada: GPT/LLM

O módulo de clusters será substituído por uma camada de inteligência que deverá:

1. analisar o produto;
2. pesquisar intenções reais de busca;
3. agrupar termos semanticamente;
4. eliminar páginas redundantes;
5. gerar conteúdo específico e útil por cluster;
6. recusar clusters sem valor suficiente.

A publicação, template, dados e sitemap permanecem os mesmos. Assim a IA pode ser trocada sem reconstruir o sistema.

## Antes de liberar indexação

Quando `cadindetudo.com` estiver conectado e as páginas piloto estiverem aprovadas:

- remover `noindex,nofollow` do template;
- configurar Google Search Console;
- validar `sitemap.xml`;
- adicionar medição de `page_view` e `cta_click`;
- só então escalar novos clusters.
