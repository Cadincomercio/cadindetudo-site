export async function onRequestPost(context) {
  let payload;

  try {
    payload = await context.request.json();
  } catch (_) {
    return new Response(null, { status: 400 });
  }

  const allowed = new Set(['page_view', 'cta_click']);
  if (!allowed.has(payload?.event)) {
    return new Response(null, { status: 422 });
  }

  const event = {
    event: String(payload.event || '').slice(0, 40),
    product: String(payload.product || '').slice(0, 180),
    page: String(payload.page || '').slice(0, 180),
    source: String(payload.source || '').slice(0, 180),
    referrer: String(payload.referrer || '').slice(0, 500),
    destination: String(payload.destination || '').slice(0, 800),
    path: String(payload.path || '').slice(0, 300),
    ts: String(payload.ts || new Date().toISOString()).slice(0, 40),
  };

  // Se uma binding do Cloudflare Analytics Engine chamada CADIN_ANALYTICS
  // estiver configurada, os eventos ficam persistidos e consultáveis.
  if (context.env?.CADIN_ANALYTICS?.writeDataPoint) {
    context.env.CADIN_ANALYTICS.writeDataPoint({
      blobs: [event.event, event.product, event.page, event.source, event.path],
      doubles: [1],
      indexes: [event.product || 'unknown'],
    });
  } else {
    // Durante a fase de validação, ainda sem binding, o evento fica visível
    // nos logs das Functions. A página nunca é bloqueada se tracking falhar.
    console.log('CADIN_EVENT', JSON.stringify(event));
  }

  return new Response(null, {
    status: 204,
    headers: {
      'cache-control': 'no-store',
    },
  });
}
