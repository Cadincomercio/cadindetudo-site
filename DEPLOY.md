# Publicação no Cloudflare Pages

Endereço público validado: https://cadindetudo-site.pages.dev

## Diagnóstico em 2026-09-05

O checkout de `main` estava no commit `c3aa88be938e26eb0ce470b47db38a489f2f3021`.
As três rotas abaixo responderam HTTP 200 no Pages, com HTML igual ao commit
(normalizando apenas finais de linha e espaço final):

- `/`
- `/controle-remoto-samsung-smart-tv-4k/`
- `/ureia-agricola-46-nitrogenio-1kg/`

Em `https://cadindetudo.com`, a home respondeu 200 com conteúdo diferente,
e as duas rotas internas responderam 404. As respostas vieram de
`Server: DPS/2.0.0+sha-9ac0622`, com cookie `dps_site_id` e referências à
GoDaddy. O DNS A retornou `76.223.105.230` e `13.248.243.5`.
Isso situa o problema observado no destino do domínio personalizado,
não na inclusão dos diretórios pelo deploy do Pages.

## Estrutura e configuração

O site estático está na raiz do repositório: `index.html`, `assets/` e
pastas de cada página com `index.html` minúsculo. `functions/api/` contém
as Pages Functions usadas pelo tracking e pela publicação de jobs.
Não existem `_redirects`, `_routes.json`, `_headers` ou configuração Wrangler
versionados no commit investigado. Não há build de framework nem workflow
de upload; os workflows existentes geram páginas e validam o engine.

A configuração compatível com essa estrutura usa a raiz do repositório como
raiz do projeto e diretório de saída, sem etapa de compilação (`exit 0`).
Os valores privados do painel, a branch de produção e o identificador do
deploy precisam ser conferidos na conta Cloudflare; não foram consultados
durante o diagnóstico por falta de sessão autenticada. O conteúdo público
comprova que pelo menos as três páginas verificadas estão publicadas.

Não adicionar um fallback `/* /index.html 200`: isso mascararia páginas
ausentes entregando a home. Não mudar templates para resolver associação DNS.

## Domínio personalizado pendente

Na conta Cloudflare, conferir o projeto Pages ligado a este repositório,
a branch `main` e a seção Custom domains. Associar `cadindetudo.com` ao
projeto e seguir as instruções DNS exibidas pelo Cloudflare. Conferir os
registros existentes antes de alterá-los, preservando serviços como email.
O domínio só deve ser considerado corrigido depois da validação de conteúdo
abaixo também passar com `--base-url https://cadindetudo.com`.

## Validação após deploy

Executar no checkout do commit publicado:

```sh
python scripts/check_public_routes.py
python scripts/check_public_routes.py --base-url https://cadindetudo.com
```

O comando exige HTTP 200 e compara o HTML de cada rota com o arquivo local.
Assim detecta tanto 404 quanto home de fallback ou conteúdo de outro site.
Aguardar a conclusão do deploy antes de verificar um commit novo.

Referências: [build e saída](https://developers.cloudflare.com/pages/configuration/build-configuration/)
e [domínios personalizados](https://developers.cloudflare.com/pages/configuration/custom-domains/).
