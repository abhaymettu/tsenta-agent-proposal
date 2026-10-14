// License scan for the resolved tree (551 Phase 1): counts licenses from every installed package.json. No network.
// Usage (in the image): node /opt/demo/license-scan.mjs /opt/openclaw/node_modules
import fs from 'node:fs';
import path from 'node:path';
const root = process.argv[2], counts = {}, unknown = [];
const walk = (dir) => {
  for (const name of fs.existsSync(dir) ? fs.readdirSync(dir) : []) {
    if (name.startsWith('.')) continue;
    const p = path.join(dir, name);
    if (name.startsWith('@')) { walk(p); continue; }
    const pj = path.join(p, 'package.json');
    if (fs.existsSync(pj)) {
      const d = JSON.parse(fs.readFileSync(pj, 'utf8'));
      const lic = typeof d.license === 'string' ? d.license : d.license?.type || (Array.isArray(d.licenses) ? d.licenses.map((l) => l.type).join(' OR ') : 'UNKNOWN');
      counts[lic] = (counts[lic] || 0) + 1;
      if (lic === 'UNKNOWN' || /GPL|AGPL|SSPL|BUSL|Commons-Clause/i.test(lic)) unknown.push(`${d.name}@${d.version}: ${lic}`);
      walk(path.join(p, 'node_modules'));
    }
  }
};
walk(root);
console.log(JSON.stringify({ total: Object.values(counts).reduce((a, b) => a + b, 0), counts, review: unknown }, null, 1));
