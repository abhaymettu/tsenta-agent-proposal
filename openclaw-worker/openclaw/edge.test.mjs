// Unit test for the edge (551 Phase 0): run with `node --test openclaw/`. Loopback only; no internet.
import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import net from 'node:net';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { allowed, edgeConnect, parseAllow, proxyServer, toolServer, startAddress } from './edge.mjs';

const listen = (s) => new Promise((r) => s.listen(0, '127.0.0.1', () => r(s.address().port)));
const close = (...ss) => Promise.all(ss.map((s) => new Promise((r) => s.close(r))));

function connectVia(port, target) {
  return new Promise((resolve) => {
    const c = net.connect(port, '127.0.0.1', () => c.write(`CONNECT ${target} HTTP/1.1\r\nHost: ${target}\r\n\r\n`));
    let buf = '';
    c.on('data', (d) => { buf += d; if (buf.includes('\r\n\r\n')) { c.destroy(); resolve(buf.split('\r\n')[0]); } });
    c.on('error', () => resolve('error'));
  });
}

test('allowlist matching is exact host:port', () => {
  const list = ['api.anthropic.com:443'];
  assert.equal(allowed('api.anthropic.com:443', list), true);
  assert.equal(allowed('API.Anthropic.com:443', list), true);
  for (const bad of ['api.anthropic.com:80', 'evil.com:443', 'api.anthropic.com.evil.com:443', 'api.anthropic.com', '', '1.2.3.4:443', 'api.anthropic.com:443/x'])
    assert.equal(allowed(bad, list), false, bad);
});

test('CONNECT to an allowlisted target tunnels; anything else is refused; plain HTTP is refused', async () => {
  const echo = net.createServer((s) => s.pipe(s));
  const echoPort = await listen(echo);
  // stand-in for the model host: the allowlist names it, the connect function maps it to the local echo server
  const proxy = proxyServer(['model.test:443'], (port, host, cb) => net.connect(echoPort, '127.0.0.1', cb));
  const p = await listen(proxy);
  assert.equal(await connectVia(p, 'model.test:443'), 'HTTP/1.1 200 Connection Established');
  assert.equal(await connectVia(p, 'example.com:443'), 'HTTP/1.1 403 Forbidden');
  assert.equal(await connectVia(p, 'model.test:80'), 'HTTP/1.1 403 Forbidden');
  const code = await new Promise((r) => http.get({ host: '127.0.0.1', port: p, path: 'http://example.com/' }, (res) => { res.resume(); r(res.statusCode); }));
  assert.equal(code, 403);
  await close(proxy, echo);
});

test('A1: only the allowlisted oc551-edge:8560 dials the bind address; others dial by name; refused targets never dial', async () => {
  const echo = net.createServer((s) => s.end()); await new Promise((r) => echo.listen(0, '127.0.0.1', r));
  const dialled = [];
  const inner = (port, host, cb) => { dialled.push(`${host}:${port}`); return net.connect(echo.address().port, '127.0.0.1', cb); };
  const proxy = proxyServer(['oc551-edge:8560', 'api.anthropic.com:443'], edgeConnect('10.9.9.9', inner));
  await new Promise((r) => proxy.listen(0, '127.0.0.1', r));
  const p = proxy.address().port;
  assert.equal(await connectVia(p, 'oc551-edge:8560'), 'HTTP/1.1 200 Connection Established');
  assert.equal(await connectVia(p, 'OC551-EDGE:8560'), 'HTTP/1.1 200 Connection Established');
  assert.equal(await connectVia(p, 'api.anthropic.com:443'), 'HTTP/1.1 200 Connection Established');
  assert.equal(await connectVia(p, 'oc551-edge:3128'), 'HTTP/1.1 403 Forbidden');
  assert.equal(await connectVia(p, 'example.com:443'), 'HTTP/1.1 403 Forbidden');
  assert.deepEqual(dialled, ['10.9.9.9:8560', '10.9.9.9:8560', 'api.anthropic.com:443'], 'refused targets are never dialled');
  proxy.close(); echo.close();
});

test('tool forward: only POST /mcp, adds the bearer from the file, passes the body through', async () => {
  let seen = null;
  const core = http.createServer((req, res) => {
    let b = ''; req.on('data', (d) => (b += d)); req.on('end', () => { seen = { auth: req.headers.authorization, path: req.url, body: b }; res.writeHead(200, { 'content-type': 'application/json' }).end('{"ok":1}'); });
  });
  const corePort = await listen(core);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'edge-'));
  fs.writeFileSync(path.join(dir, 'tok'), 'per-boot-token\n', { mode: 0o600 });
  const fwd = toolServer(`http://127.0.0.1:${corePort}/mcp`, path.join(dir, 'tok'));
  const fp = await listen(fwd);
  const req = (method, p, body) => new Promise((r) => {
    const q = http.request({ host: '127.0.0.1', port: fp, method, path: p, headers: { 'content-type': 'application/json', authorization: 'Bearer worker-should-not-matter' } }, (res) => { let d = ''; res.on('data', (x) => (d += x)); res.on('end', () => r([res.statusCode, d])); });
    if (body) q.write(body); q.end();
  });
  assert.deepEqual(await req('POST', '/mcp', '{"jsonrpc":"2.0","id":1,"method":"ping"}'), [200, '{"ok":1}']);
  assert.deepEqual(seen, { auth: 'Bearer per-boot-token', path: '/mcp', body: '{"jsonrpc":"2.0","id":1,"method":"ping"}' });
  assert.equal((await req('GET', '/mcp'))[0], 404);
  assert.equal((await req('POST', '/api/reset', '{}'))[0], 404, 'the worker cannot reach the core UI API');
  await close(fwd, core);
  fs.rmSync(dir, { recursive: true });
});

test('the edge binds to its single start network and refuses to guess with more than one', () => {
  const nic = (address, internal = false) => ({ family: 'IPv4', address, internal });
  assert.equal(startAddress({ lo: [nic('127.0.0.1', true)], eth0: [nic('172.30.0.2')] }), '172.30.0.2');
  assert.throws(() => startAddress({ eth0: [nic('172.30.0.2')], eth1: [nic('172.31.0.2')] }));
  assert.throws(() => startAddress({ lo: [nic('127.0.0.1', true)] }));
});

test('tool forward with no token pushed yet answers 503 and stays up', async () => {
  const fwd = toolServer('http://127.0.0.1:9/mcp', path.join(os.tmpdir(), 'edge-no-such-token-file'));
  const fp = await listen(fwd);
  const post = () => new Promise((r) => { const q = http.request({ host: '127.0.0.1', port: fp, method: 'POST', path: '/mcp' }, (res) => { res.resume(); r(res.statusCode); }); q.end('{}'); });
  assert.equal(await post(), 503);
  assert.equal(await post(), 503, 'still listening after the first refusal');
  await close(fwd);
});

test('EDGE_ALLOW parsing: unset, empty, list; a string allowlist never matches', () => {
  assert.deepEqual(parseAllow(undefined), ['api.anthropic.com:443']);
  assert.deepEqual(parseAllow(''), []);
  assert.deepEqual(parseAllow(' A.example:443 , b.example:8443,'), ['a.example:443', 'b.example:8443']);
  assert.equal(allowed('anthropic.com:443', parseAllow(undefined)), false, 'no substring match');
  assert.equal(allowed('c.com:443', parseAllow(undefined)), false, 'no substring match (551 RC2 exact case)');
  assert.equal(allowed('i.anthropic.com:443', parseAllow(undefined)), false);
  assert.equal(allowed('api.anthropic.com:443', parseAllow('')), false);
  assert.equal(allowed('anthropic.com:443', 'api.anthropic.com:443'), false, 'a string allowlist is refused outright');
  assert.equal(allowed('api.anthropic.com:443', 'api.anthropic.com:443'), false);
});
