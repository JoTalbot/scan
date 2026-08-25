// Vercel Serverless Worker для RouterScan
// Проверка HTTP-баннеров списка IP (маленькие батчи, как в e2b_targets_audit)
//
// Запрос: POST /api/audit  { "targets": ["1.2.3.4", ...], "mode": "http" }
// Ответ: { "results": [{ip, status, server, len}, ...] }
//
// Лимиты Vercel Hobby: serverless functions до 300s (Hobby), Node.js runtime.
// ВАЖНО: Node.js https запросы блокируются по времени — используем короткие
// таймауты и НЕбольшие батчи (до 20 IP на запрос).

const https = require('https');
const http = require('http');

function fetchUrl(ip, port, timeoutMs) {
  return new Promise((resolve) => {
    const mod = port === 443 ? https : http;
    const req = mod.get({
      host: ip,
      port: port,
      path: '/',
      headers: { 'User-Agent': 'Mozilla/5.0 (RouterScan Vercel Worker)', 'Connection': 'close' },
      timeout: timeoutMs,
    }, (res) => {
      let data = '';
      res.on('data', (c) => { data += c; if (data.length > 4096) req.destroy(); });
      res.on('end', () => {
        resolve({
          ip, port,
          status: res.statusCode,
          server: res.headers['server'] || '',
          len: data.length,
        });
      });
    });
    req.on('timeout', () => { req.destroy(); resolve({ ip, port, status: 'timeout' }); });
    req.on('error', (e) => { resolve({ ip, port, status: 'error', error: e.code || String(e).slice(0, 60) }); });
  });
}

module.exports = async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.status(200).end(); return; }

  if (req.method !== 'POST') {
    res.status(405).json({ error: 'POST only' });
    return;
  }

  let body = '';
  req.on('data', (c) => { body += c; if (body.length > 10000) req.destroy(); });
  req.on('end', async () => {
    try {
      const { targets = [], mode = 'http', port = 80, timeout = 3000 } = JSON.parse(body || '{}');
      if (!Array.isArray(targets) || targets.length === 0) {
        res.status(400).json({ error: 'targets required' });
        return;
      }
      if (targets.length > 50) {
        res.status(400).json({ error: 'max 50 targets per request' });
        return;
      }

      const results = [];
      // последовательно (небольшой батч, короткий таймаут)
      for (const ip of targets) {
        if (mode === 'http') {
          results.push(await fetchUrl(ip, port, timeout));
        } else if (mode === 'reach') {
          // проверка нескольких портов
          const open = [];
          for (const p of [80, 443, 8080, 8443]) {
            const r = await fetchUrl(ip, p, 2000);
            if (r.status && typeof r.status === 'number') open.push(p);
          }
          results.push({ ip, open });
        }
      }
      res.status(200).json({ count: results.length, results });
    } catch (e) {
      res.status(500).json({ error: String(e).slice(0, 200) });
    }
  });
};
