# Tracking da Máquina de Captura de Demanda

O site registra dois eventos próprios antes de o visitante sair para o Mercado Livre:

- `page_view`
- `cta_click`

## Dados enviados

Cada evento inclui:

- `product`: ID/título do produto
- `page`: slug da landing page
- `source`: origem inferida do referrer, como `google`, `bing`, `chatgpt` ou domínio de referência
- `referrer`
- `destination`: URL do Mercado Livre
- `path`
- `ts`: timestamp ISO

O JavaScript está em `assets/tracking.js` e envia os dados para `/api/event`.

## Endpoint

`functions/api/event.js` recebe os eventos como Cloudflare Pages Function.

### Fase atual

Sem binding persistente, os eventos são registrados nos logs da Function. Isso permite validar o fluxo sem adicionar serviços externos.

### Persistência recomendada antes de liberar indexação

Criar no Cloudflare um binding do **Analytics Engine** com o nome:

`CADIN_ANALYTICS`

O endpoint detecta automaticamente esse binding e passa a gravar os eventos com `writeDataPoint`.

A liberação de `noindex,nofollow` deve ocorrer somente depois de:

1. domínio `cadindetudo.com` conectado;
2. tracking persistente validado;
3. Search Console configurado;
4. sitemap submetido.
