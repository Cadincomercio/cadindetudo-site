(() => {
  const body = document.body;
  if (!body) return;

  const endpoint = '/api/event';
  const product = body.dataset.product || '';
  const page = body.dataset.page || location.pathname;
  const destination = body.dataset.destination || '';

  function sourceFromReferrer() {
    const ref = document.referrer || '';
    if (!ref) return 'direct';
    try {
      const host = new URL(ref).hostname;
      if (host.includes('google.')) return 'google';
      if (host.includes('bing.')) return 'bing';
      if (host.includes('chatgpt.com')) return 'chatgpt';
      return host;
    } catch (_) {
      return 'unknown';
    }
  }

  function send(eventName, extra = {}) {
    const payload = {
      event: eventName,
      product,
      page,
      source: sourceFromReferrer(),
      referrer: document.referrer || '',
      destination,
      path: location.pathname,
      ts: new Date().toISOString(),
      ...extra,
    };

    const data = JSON.stringify(payload);
    if (navigator.sendBeacon) {
      navigator.sendBeacon(endpoint, new Blob([data], { type: 'application/json' }));
      return;
    }

    fetch(endpoint, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: data,
      keepalive: true,
    }).catch(() => {});
  }

  send('page_view');

  document.querySelectorAll('[data-cadin-cta="mercado-livre"]').forEach((link) => {
    link.addEventListener('click', () => {
      send('cta_click', { href: link.href });
    });
  });
})();
