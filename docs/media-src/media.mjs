// Draws docs/evidence-check.png and docs/social-preview.png from the real files and the real checker output.
// Run by build.sh. Env: WORK (the scratch folder build.sh made), ROOT (the repo root), PLAYWRIGHT_DIR.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
const { chromium } = createRequire(path.resolve(process.env.PLAYWRIGHT_DIR || '.') + '/')('playwright');

const WORK = process.env.WORK;
const ROOT = process.env.ROOT;
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const read = (p) => fs.readFileSync(p, 'utf8');

// Real checker verdicts: plan 001 and the bad draft 002 side by side.
const both = path.join(WORK, 'plans-both');
fs.rmSync(both, { recursive: true, force: true });
fs.mkdirSync(both);
fs.copyFileSync(path.join(WORK, 'plans', '001-use-decimal-for-money.md'), path.join(both, '001-use-decimal-for-money.md'));
fs.copyFileSync(path.join(WORK, 'drafts', '002-fix-sql-injection-in-orders.md'), path.join(both, '002-fix-sql-injection-in-orders.md'));
let raw;
try {
  raw = execFileSync('python3', ['check_plans.py', 'plans-both', '--repo', '.', '--json'], { cwd: WORK, encoding: 'utf8' });
} catch (e) { raw = e.stdout; }   // exit code 1 is the point of the demo
const report = JSON.parse(raw);
const find = (name) => report.plans.find((p) => p.file.startsWith(name));
const good = find('001'), bad = find('002');
const badEvidence = bad.findings.find((f) => f.code === 'evidence-unresolved');
const count = (p, lvl) => p.findings.filter((f) => f.level === lvl).length;
const nGood = { e: count(good, 'error'), w: count(good, 'warning') };
if (good.findings.some((f) => f.level === 'error') || !badEvidence) throw new Error('unexpected checker result');

// Plan 001: the evidence bullets that cite pricing.py, copied from the plan file.
const plan1 = read(path.join(WORK, 'plans', '001-use-decimal-for-money.md')).split('\n');
const cite = (line) => { const m = line.match(/^- `([^`]+):(\d+)` `([^`]+)`/); return m && { file: m[1], line: +m[2], quote: m[3] }; };
const goodCites = plan1.map(cite).filter((c) => c && c.file.endsWith('shop/pricing.py'));
const pricing = read(path.join(WORK, 'examples/demo-shop/shop/pricing.py')).replace(/\n$/, '').split('\n');
// Plan 002: its one bogus citation.
const plan2 = read(path.join(WORK, 'drafts', '002-fix-sql-injection-in-orders.md')).split('\n');
const badCite = plan2.map(cite).find((c) => c);
const orders = read(path.join(WORK, 'examples/demo-shop/shop/orders.py')).replace(/\n$/, '').split('\n');

const code = (lines, marks, tag, ghost = 0) =>
  lines.map((t, i) => `<div class="cl ${marks.includes(i + 1) ? 'hit' : ''}" id="${tag}${i + 1}"><b>${i + 1}</b><span>${esc(t) || '&nbsp;'}</span></div>`).join('') +
  Array.from({ length: ghost }, (_, k) => `<div class="cl ghost" id="${tag}${lines.length + k + 1}"><b>${lines.length + k + 1}</b><span>(no such line)</span></div>`).join('');

const bullets = (cs, prefix) => cs.map((c, i) => `<div class="bul" id="${prefix}${i}"><div class="ref">${esc(c.file)}:${c.line}</div><div class="q">${esc(c.quote)}</div></div>`).join('');

const html = `<style>
*{box-sizing:border-box}body{margin:0;background:#12141c;color:#e6e9f5;font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif}
.wrap{width:1440px;padding:44px 40px 40px;position:relative}
h1{margin:0 0 6px;font-size:34px;letter-spacing:-.3px}.sub{color:#9aa1bd;font-size:18px;margin-bottom:30px}
.row{display:grid;grid-template-columns:560px 1fr 700px;align-items:start;margin-bottom:30px}
.card{background:#1b1e2b;border:1px solid #2c3042;border-radius:12px;overflow:hidden}
.card h3{margin:0;padding:10px 16px;background:#232739;font:600 14px 'DejaVu Sans Mono',Menlo,monospace;color:#b6bcd6}
.card h3 em{font-style:normal;color:#8890b0;font-weight:400}
.body{padding:12px 16px}
.bul{margin:0 0 12px;padding:8px 10px;border-radius:8px;background:#14172100}
.ref{font:600 13px 'DejaVu Sans Mono',Menlo,monospace;color:#f4b860}
.q{font:13px 'DejaVu Sans Mono',Menlo,monospace;color:#e6e9f5;margin-top:4px;word-break:break-all}
.cl{display:flex;font:13px/24px 'DejaVu Sans Mono',Menlo,monospace;white-space:pre;height:24px;padding-right:8px}
.cl b{width:34px;text-align:right;color:#6b7290;font-weight:400;padding-right:12px;flex:none}
.cl.hit{background:#4a3a14}.cl.hit span{color:#fff}
.cl.ghost{background:#3a1b22;color:#ff9a9a}.cl.ghost b{color:#ff9a9a}
.verdict{margin-top:14px;font:14px 'DejaVu Sans Mono',Menlo,monospace;padding:10px 14px;border-radius:8px}
.v-ok{background:#12301f;color:#7ee787;border:1px solid #1f5a37}.v-bad{background:#3a1b22;color:#ff9a9a;border:1px solid #6b2b36}
.tag{display:inline-block;font:700 13px 'DejaVu Sans Mono',monospace;border-radius:6px;padding:2px 8px;margin-right:8px}
.t-ok{background:#1f5a37;color:#c9ffd9}.t-bad{background:#7a2535;color:#ffd5d5}
.mid{position:relative;height:100%}
.label{font-size:13px;color:#9aa1bd;margin:0 0 8px 2px;text-transform:uppercase;letter-spacing:.8px}
.foot{color:#8890b0;font-size:14px;margin-top:6px}
svg{position:absolute;left:0;top:0;pointer-events:none}
</style>
<div class="wrap" id="wrap">
<h1>Every finding is checked against the real file</h1>
<div class="sub">check_plans.py opens each cited file and compares the quoted code with the line. A finding the code does not back fails.</div>

<div class="row" id="rowA">
  <div><div class="label">A plan that holds up</div><div class="card"><h3>plans/${esc(good.file)} <em>## Evidence</em></h3><div class="body">${bullets(goodCites, 'ga')}</div></div></div>
  <div></div>
  <div><div class="label">The real file</div><div class="card"><h3>examples/demo-shop/shop/pricing.py</h3><div class="body">${code(pricing, goodCites.map((c) => c.line), 'P')}</div></div></div>
</div>
<div class="verdict v-ok"><span class="tag t-ok">ok</span>${esc(good.file)} &nbsp; ${nGood.e} errors, ${nGood.w} warnings</div>

<div style="height:34px"></div>
<div class="row" id="rowB">
  <div><div class="label">A plan with an invented finding</div><div class="card"><h3>plans/${esc(bad.file)} <em>## Evidence</em></h3><div class="body">${bullets([badCite], 'ba')}</div></div></div>
  <div></div>
  <div><div class="label">The real file</div><div class="card"><h3>examples/demo-shop/shop/orders.py</h3><div class="body">${code(orders, [], 'O', 4)}</div></div></div>
</div>
<div class="verdict v-bad"><span class="tag t-bad">FAIL</span>${esc(bad.file)}<br><span style="margin-left:62px">error&nbsp;&nbsp;&nbsp;line ${badEvidence.line}&nbsp;&nbsp;&nbsp;[${esc(badEvidence.code)}] ${esc(badEvidence.message)}</span></div>
<div class="foot">Quotes, code and verdicts are copied from real files and real checker output. The red rows only mark lines the file does not have. Plan 002 is a bad draft written for this demo.</div>
<svg id="arrows" width="1440" height="1200"></svg>
</div>`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
await page.setContent(html);
await page.evaluate(({ goodCites, badLine }) => {
  const svg = document.getElementById('arrows');
  const wrap = document.getElementById('wrap').getBoundingClientRect();
  const link = (fromId, toId, color, dashed) => {
    const a = document.getElementById(fromId).getBoundingClientRect();
    const b = document.getElementById(toId).getBoundingClientRect();
    const x1 = a.right - wrap.left, y1 = a.top + a.height / 2 - wrap.top;
    const x2 = b.left - wrap.left, y2 = b.top + b.height / 2 - wrap.top;
    const mx = (x1 + x2) / 2;
    svg.insertAdjacentHTML('beforeend', `<path d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2 - 6},${y2}" fill="none" stroke="${color}" stroke-width="2.2" ${dashed ? 'stroke-dasharray="7 5"' : ''}/><path d="M${x2},${y2} l-9,-5 l0,10 z" fill="${color}"/>`);
  };
  goodCites.forEach((c, i) => link('ga' + i, 'P' + c.line, '#f4b860', false));
  link('ba0', 'O' + badLine, '#ff7b72', true);
  svg.setAttribute('height', document.getElementById('wrap').scrollHeight);
}, { goodCites, badLine: badCite.line });
await page.locator('#wrap').screenshot({ path: path.join(WORK, 'evidence-check.png') });

// Social preview: 1280 x 640.
const logo = fs.readFileSync(path.join(ROOT, 'agensi/media/logo.png')).toString('base64');
const social = await browser.newPage({ viewport: { width: 1280, height: 640 }, deviceScaleFactor: 1 });
await social.setContent(`<style>
*{box-sizing:border-box}body{margin:0;width:1280px;height:640px;background:linear-gradient(135deg,#b45309,#451a03);font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif;color:#fff;display:flex;flex-direction:column;justify-content:center;padding:0 90px}
.top{display:flex;align-items:center;gap:36px}img{width:170px;height:170px;border-radius:38px;box-shadow:0 14px 40px rgba(0,0,0,.35)}
h1{margin:0;font-size:84px;letter-spacing:-1.5px;line-height:1}p{margin:14px 0 0;font-size:34px;line-height:1.25;color:#ffe9cf;max-width:760px}
.term{margin-top:46px;background:#12141c;border-radius:14px;padding:20px 26px;font:24px/1.55 'DejaVu Sans Mono',Menlo,monospace;width:max-content;box-shadow:0 14px 40px rgba(0,0,0,.35)}
.ok{color:#7ee787}.bad{color:#ff7b72}.dim{color:#8b90a8}
</style><div class="top"><img src="data:image/png;base64,${logo}" alt=""><div><h1>Repo Audit Planner</h1><p>Audit any repo. Get work orders a cheaper agent can run, with every finding checked against the code.</p></div></div>
<div class="term"><div class="dim">$ python3 check_plans.py plans --repo .</div><div class="ok">ok&nbsp;&nbsp;&nbsp;&nbsp;${esc(good.file)}</div><div class="bad">FAIL&nbsp;&nbsp;${esc(bad.file)}</div><div class="bad">&nbsp;&nbsp;error [${esc(badEvidence.code)}] ...${esc(badEvidence.message.split('/').pop())}</div></div>`);
await social.screenshot({ path: path.join(WORK, 'social-preview.png') });
await browser.close();
console.log('wrote evidence-check.png and social-preview.png');
