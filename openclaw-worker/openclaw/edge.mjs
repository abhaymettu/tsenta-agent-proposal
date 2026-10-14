// oc551-edge: the worker's only way out (551 contract s9.3). Two listeners, no inbound relay, no other routes.
//   :3128  forward proxy, CONNECT only, to exactly the allowlisted host:port (the model API). Everything else: 403.
//   :8560  tool forward: POST /mcp only, to the host core's MCP endpoint, adding the core's bearer token, which the
//          edge reads from a mounted file. The worker holds no tool credential.
// Every decision is one JSON line on stdout (host:port and verdict only; never headers or bodies).
import http from 'node:http';
import net from 'node:net';
import fs from 'node:fs';
import os from 'node:os';

// EDGE_ALLOW: unset = the model API only; set but empty = nothing (the canary); else comma-separated host:port entries.
export function parseAllow(env) {
  return (env ?? 'api.anthropic.com:443').split(',').map((x) => x.trim().toLowerCase()).filter(Boolean);
}

export function allowed(target, allowlist) {
  if (!Array.isArray(allowlist)) return false;  // a string allowlist would substring-match (canary run 19:38 found this)
  const m = /^([a-z0-9.-]+):(\d{1,5})$/i.exec(String(target || ''));
  return !!m && allowlist.includes(`${m[1].toLowerCase()}:${m[2]}`);
}

const log = (o) => process.stdout.write(JSON.stringify({ at: new Date().toISOString(), ...o }) + '\n');

export function proxyServer(allowlist, connect = net.connect) {
  const s = http.createServer((req, res) => { log({ op: 'http', verdict: 'refused', target: req.headers.host || '' }); res.writeHead(403).end('CONNECT only\n'); });
  s.headersTimeout = 10000; s.requestTimeout = 10000;
  s.on('connect', (req, client, head) => {
    if (!allowed(req.url, allowlist)) {
      log({ op: 'CONNECT', target: req.url, verdict: 'refused' });
      client.end('HTTP/1.1 403 Forbidden\r\n\r\n');
      return;
    }
    const [host, port] = req.url.split(':');
    client.setTimeout(TUNNEL_IDLE_MS, () => client.destroy());
    const up = connect(+port, host, () => {
      log({ op: 'CONNECT', target: req.url, verdict: 'allowed' });
      client.write('HTTP/1.1 200 Connection Established\r\n\r\n');
      if (head.length) up.write(head);
      up.pipe(client); client.pipe(up);
    });
    up.on('error', () => { log({ op: 'CONNECT', target: req.url, verdict: 'upstream-error' }); client.destroy(); });
    client.on('error', () => up.destroy());
  });
  return s;
}

const MAX_BODY = 1 << 20, TUNNEL_IDLE_MS = 120000, TOOL_TIMEOUT_MS = 30000;

export function toolServer(upstream, tokenFile) {
  return http.createServer((req, res) => {
    if (+(req.headers['content-length'] || 0) > MAX_BODY) { log({ op: 'tool', verdict: 'refused', reason: 'too large' }); res.writeHead(413).end(); return; }
    if (req.method !== 'POST' || req.url !== '/mcp') {
      log({ op: 'tool', verdict: 'refused', method: req.method, path: req.url });
      res.writeHead(404).end();
      return;
    }
    let token = '';
    try { token = fs.readFileSync(tokenFile, 'utf8').trim(); } catch {}
    if (!token) { log({ op: 'tool', verdict: 'refused', reason: 'no token' }); res.writeHead(503).end(); return; }  // not pushed yet
    const u = new URL(upstream);
    const headers = { 'content-type': req.headers['content-type'] || 'application/json', accept: req.headers.accept || 'application/json, text/event-stream',
      authorization: 'Bearer ' + token };
    if (req.headers['mcp-protocol-version']) headers['mcp-protocol-version'] = req.headers['mcp-protocol-version'];
    if (req.headers['mcp-session-id']) headers['mcp-session-id'] = req.headers['mcp-session-id'];
    const up = http.request({ host: u.hostname, port: u.port, path: u.pathname, method: 'POST', headers }, (r) => {
      log({ op: 'tool', verdict: 'forwarded', status: r.statusCode });
      res.writeHead(r.statusCode, { 'content-type': r.headers['content-type'] || 'application/json' });
      r.pipe(res);
    });
    up.setTimeout(TOOL_TIMEOUT_MS, () => up.destroy(new Error('timeout')));
    up.on('error', () => { log({ op: 'tool', verdict: 'upstream-error' }); if (!res.headersSent) res.writeHead(502); res.end(); });
    let n = 0;
    req.on('data', (d) => { n += d.length; if (n > MAX_BODY) { up.destroy(); req.destroy(); } });
    req.pipe(up);
  });
}

// 551 v43 A1: the Gateway reaches its MCP server through this proxy (its proxy is process-wide), so the allowlist names
// oc551-edge:8560. Inside the edge, its own name resolves to both of its networks (/etc/hosts lists both), so that one exact
// target is dialled at the bind address, where the tool listener is. Every other target dials by name as before.
export function edgeConnect(bind, connect = net.connect) {
  return (port, host, cb) => connect(port, String(host).toLowerCase() === 'oc551-edge' && +port === 8560 ? bind : host, cb);
}

// The edge starts attached to oc551-int only; the address it has at that moment is where both listeners bind, so the
// later oc551-ext leg (egress) and the default bridge never see :3128 or :8560 (551 review F4).
export function startAddress(ifaces = os.networkInterfaces()) {
  const a = Object.values(ifaces).flat().filter((x) => x && x.family === 'IPv4' && !x.internal);
  if (a.length !== 1) throw new Error(`edge: expected exactly one network at start, found ${a.length}`);
  return a[0].address;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const bind = process.env.EDGE_BIND || startAddress();
  const allow = parseAllow(process.env.EDGE_ALLOW);
  proxyServer(allow, edgeConnect(bind)).listen(3128, bind, () => log({ op: 'start', bind, proxy: 3128, allow }));
  toolServer(process.env.TOOL_UPSTREAM || 'http://host.docker.internal:8550/mcp', process.env.TOOL_TOKEN_FILE || '/run/secrets/mcp_token')
    .listen(8560, bind, () => log({ op: 'start', bind, tools: 8560 }));
}
