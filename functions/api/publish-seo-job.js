const jsonResponse = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'access-control-allow-origin': '*',
    },
  });

export async function onRequestOptions() {
  return new Response(null, {
    status: 204,
    headers: {
      'access-control-allow-origin': '*',
      'access-control-allow-methods': 'POST, OPTIONS',
      'access-control-allow-headers': 'X-Cadin-Secret, Authorization, Content-Type',
      'access-control-max-age': '86400',
    },
  });
}

function extractJob(payload) {
  if (payload && typeof payload.job_json === 'string') {
    try {
      return JSON.parse(payload.job_json);
    } catch (_) {
      throw new Error('job_json não contém JSON válido');
    }
  }
  return payload;
}

export async function onRequestPost(context) {
  const customHeader = String(context.request.headers.get('x-cadin-secret') || '').trim();
  const authorization = String(context.request.headers.get('authorization') || '').trim();
  const bearerHeader = authorization.toLowerCase().startsWith('bearer ')
    ? authorization.slice(7).trim()
    : '';
  const expected = String(context.env?.CADIN_API_SECRET || '').trim();

  if (!expected) {
    return jsonResponse({ ok: false, error: 'CADIN_API_SECRET não configurado' }, 500);
  }

  if (customHeader !== expected && bearerHeader !== expected) {
    return jsonResponse({ ok: false, error: 'Não autorizado' }, 401);
  }

  let payload;
  try {
    payload = await context.request.json();
  } catch (_) {
    return jsonResponse({ ok: false, error: 'JSON inválido' }, 400);
  }

  let job;
  try {
    job = extractJob(payload);
  } catch (err) {
    return jsonResponse({ ok: false, error: err.message }, 422);
  }

  const required = ['version', 'publish', 'product', 'research', 'pages'];
  const missing = required.filter((key) => job?.[key] === undefined || job?.[key] === null);
  if (missing.length) {
    return jsonResponse({ ok: false, error: `Campos obrigatórios ausentes: ${missing.join(', ')}` }, 422);
  }

  if (!Array.isArray(job.pages) || job.pages.length < 1 || job.pages.length > 12) {
    return jsonResponse({ ok: false, error: 'pages precisa conter de 1 a 12 páginas' }, 422);
  }

  const githubToken = String(context.env?.GITHUB_TOKEN || '').trim();
  if (!githubToken) {
    return jsonResponse({ ok: false, error: 'GITHUB_TOKEN não configurado' }, 500);
  }

  const gh = await fetch('https://api.github.com/repos/Cadincomercio/cadindetudo-site/dispatches', {
    method: 'POST',
    headers: {
      'authorization': `Bearer ${githubToken}`,
      'accept': 'application/vnd.github+json',
      'x-github-api-version': '2022-11-28',
      'content-type': 'application/json',
      'user-agent': 'Cadin-SEO-Engine',
    },
    body: JSON.stringify({
      event_type: 'seo_job',
      client_payload: job,
    }),
  });

  if (!gh.ok) {
    let detail = '';
    try {
      detail = await gh.text();
    } catch (_) {}
    return jsonResponse({
      ok: false,
      error: 'GitHub recusou o job',
      github_status: gh.status,
      detail: detail.slice(0, 1000),
    }, 502);
  }

  return jsonResponse({
    ok: true,
    accepted: true,
    message: 'Job recebido e enviado ao GitHub para publicação',
    pages: job.pages.length,
    item_id: job?.product?.item_id || null,
  });
}
