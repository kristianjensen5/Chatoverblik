// Browser-smoke-test af den faktiske CSP (blocker B1).
//
// Baggrund: P0-hardeningen indførte `script-src 'self' 'nonce-…'` uden
// `unsafe-inline`. Den daværende test tjekkede kun CSP-*teksten* i
// chatoverblik.py — ikke at appen faktisk kører under den. Derfor overlevede
// tre inline `onclick` i index.html, hvoraf én gjorde 📋 Kopiér sti helt død.
// Denne test kører den rigtige app i en rigtig browser under den rigtige CSP.
//
// Kør:
//   1) start serveren (start.command eller python3 chatoverblik.py)
//   2) npx playwright@1.62 install chromium     # kun første gang
//   3) node tests/test_b1_csp_browser.mjs
//
// Kræver Node + Playwright (dev-only — indgår ikke i release_manifest.json,
// og appen selv er fortsat Python stdlib uden pip-deps).

import { chromium } from 'playwright';

const BASE = process.env.CC_BASE_URL || 'http://localhost:7777';
const results = [];
const cspViolations = [];

function record(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' — ' + detail : ''}`);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({
  permissions: ['clipboard-read', 'clipboard-write'],
});
const page = await ctx.newPage();

page.on('console', (m) => {
  const t = m.text();
  if (/Content Security Policy|Refused to execute inline|unsafe-inline/i.test(t)) {
    cspViolations.push(t);
  }
});
page.on('pageerror', (e) => cspViolations.push('pageerror: ' + e.message));

// Blokér ægte udgående navigation fra url-chips
await page.route(/^https?:\/\/(?!localhost:7777)/, (r) => r.abort());

await page.goto(BASE + '/', { waitUntil: 'networkidle' });
await page.waitForSelector('details.project-group', { timeout: 20000 });

// ---------------------------------------------------------------- Test A
// Klik på en projekt-header-knap må IKKE folde projektgruppen sammen.
const groupWithBtn = page.locator('details.project-group')
  .filter({ has: page.locator('.proj-header-actions button[data-action="browse-files"]') })
  .first();

await groupWithBtn.locator('summary .proj-header-name').click();
await page.waitForTimeout(300);
const openBefore = await groupWithBtn.evaluate((d) => d.open);

await groupWithBtn.locator('button[data-action="browse-files"]').click();
await page.waitForTimeout(700);
const openAfterBtn = await groupWithBtn.evaluate((d) => d.open);
const modalOpen = await page.locator('#modal, .modal').first().isVisible().catch(() => false);

record('A1 projekt-header-knap folder ikke gruppen',
  openBefore === openAfterBtn,
  `open før=${openBefore} efter=${openAfterBtn}`);
record('A2 knappen udfører sin handling (Filer-modal åbner)', modalOpen === true,
  `modal synlig=${modalOpen}`);

await page.keyboard.press('Escape');
await page.locator('.modal-backdrop, #modal').first()
  .click({ position: { x: 5, y: 5 }, timeout: 1500 }).catch(() => {});
await page.waitForTimeout(300);

// ---------------------------------------------------------------- Test B
// Klik på en url-chip må ikke folde gruppen (chippen åbner sin egen fane).
const groupWithChip = page.locator('details.project-group')
  .filter({ has: page.locator('a.url-chip') }).first();

if ((await groupWithChip.count()) === 0) {
  record('B url-chip folder ikke gruppen', true, 'sprunget over — ingen url-chips i data');
} else {
  const gid = await groupWithChip.getAttribute('data-gid');
  if (!(await groupWithChip.evaluate((d) => d.open))) {
    await groupWithChip.locator('summary .proj-header-name').click();
    await page.waitForTimeout(300);
  }
  const chipOpenBefore = await groupWithChip.evaluate((d) => d.open);
  const popupP = page.waitForEvent('popup', { timeout: 3000 }).catch(() => null);
  await groupWithChip.locator('a.url-chip').first().click();
  const popup = await popupP;
  if (popup) await popup.close().catch(() => {});
  await page.waitForTimeout(500);
  const chipOpenAfter = await page.evaluate(
    (g) => document.querySelector(`details.project-group[data-gid="${g}"]`)?.open, gid);
  record('B url-chip folder ikke gruppen', chipOpenBefore === chipOpenAfter,
    `open før=${chipOpenBefore} efter=${chipOpenAfter}`);
}

// ---------------------------------------------------------------- Test C
// "Server kører ikke"-badge: 📋 Kopiér sti skal virke (var død under CSP).
await page.route('**/api/sessions*', (r) => r.abort());
await page.waitForSelector('.server-health.dead .app-path-copy', { timeout: 20000 });
const copyBtn = page.locator('.app-path-copy').first();
await copyBtn.click();
await page.waitForTimeout(600);
const copyLabel = (await copyBtn.textContent()) || '';
const clip = await page.evaluate(() => navigator.clipboard.readText()).catch(() => '');
record('C 📋 Kopiér sti virker', copyLabel.includes('Kopieret') || clip.length > 0,
  `knaptekst="${copyLabel.trim()}" clipboard="${clip}"`);

// ---------------------------------------------------------------- Test D
record('D ingen CSP-violations i konsollen', cspViolations.length === 0,
  cspViolations.length ? cspViolations.slice(0, 6).join(' | ') : 'konsol ren');

await browser.close();

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} bestået`);
process.exit(failed.length ? 1 : 0);
