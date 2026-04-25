#!/usr/bin/env node
/**
 * Iris PDF generator (Node + Playwright).
 *
 * Loops over every edition in `site/src/content/editions/*.mdx`,
 * loads the print-layout route from a running Astro preview server,
 * and writes the resulting PDF to `site/dist/downloads/{id}.pdf`.
 *
 * Usage:
 *   node scripts/generate-pdfs.mjs                       # default site URL
 *   node scripts/generate-pdfs.mjs --site-url http://localhost:4321
 *   node scripts/generate-pdfs.mjs --month 2026-02       # one edition only
 *   node scripts/generate-pdfs.mjs --output dist         # output dir under site/
 *
 * Designed for both local dev and the Azure SWA CI workflow. The script
 * does NOT start the Astro preview server — caller is responsible for
 * that (and shutting it down afterwards).
 */
import { mkdir, readdir, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Script lives at site/scripts/generate-pdfs.mjs, so the repo root is two up.
const PROJECT_ROOT = path.resolve(__dirname, '..', '..');

function parseArgs(argv) {
  const args = { siteUrl: 'http://localhost:4321', month: null, output: 'dist/downloads' };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--site-url') args.siteUrl = argv[++i];
    else if (a === '--month') args.month = argv[++i];
    else if (a === '--output') args.output = argv[++i];
    else if (a === '--help' || a === '-h') {
      console.log(
        'Usage: generate-pdfs.mjs [--site-url URL] [--month YYYY-MM] [--output DIR]',
      );
      process.exit(0);
    } else {
      console.error(`Unknown argument: ${a}`);
      process.exit(2);
    }
  }
  return args;
}

async function listEditionIds(filter) {
  const editionsDir = path.join(PROJECT_ROOT, 'site', 'src', 'content', 'editions');
  if (!existsSync(editionsDir)) {
    console.error(`Editions directory missing: ${editionsDir}`);
    process.exit(2);
  }
  const files = await readdir(editionsDir);
  const ids = files
    .filter((f) => f.endsWith('.mdx'))
    .map((f) => f.replace(/\.mdx$/, ''))
    .filter((id) => /^\d{4}-\d{2}$/.test(id));
  if (filter) return ids.includes(filter) ? [filter] : [];
  return ids.sort();
}

async function waitForServer(siteUrl, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(siteUrl, { signal: AbortSignal.timeout(2000) });
      if (res.ok || res.status === 404) return; // 404 is fine, server is up
    } catch {
      /* not ready yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`No Astro preview at ${siteUrl} after ${timeoutMs}ms`);
}

async function generateOne(browser, siteUrl, month, outDir) {
  const url = `${siteUrl.replace(/\/+$/, '')}/editions/${month}/print-layout/`;
  const target = path.join(outDir, `${month}.pdf`);
  console.log(`→ ${month}: rendering ${url}`);

  const ctx = await browser.newContext({
    viewport: { width: 1240, height: 1754 },
    deviceScaleFactor: 2,
  });
  const page = await ctx.newPage();
  try {
    const res = await page.goto(url, { waitUntil: 'networkidle', timeout: 30_000 });
    if (!res || !res.ok()) {
      throw new Error(`Failed to load ${url}: status ${res?.status()}`);
    }
    // Wait for fonts and any inline SVGs to settle.
    await page.evaluate(() => (document.fonts ? document.fonts.ready : Promise.resolve()));
    await page.waitForTimeout(400);

    const footer = `<div style="font-size: 8pt; color: #999999; width: 100%; text-align: center;
      padding: 0 18mm; font-family: Lato, Arial, sans-serif;">
      Iris, ${month} &middot; page <span class="pageNumber"></span>
      of <span class="totalPages"></span>
      &middot; iris.cefic.org</div>`;

    await page.pdf({
      path: target,
      format: 'A4',
      margin: { top: '18mm', bottom: '18mm', left: '18mm', right: '18mm' },
      printBackground: true,
      displayHeaderFooter: true,
      footerTemplate: footer,
      headerTemplate: '<div></div>',
    });
    const stats = await stat(target);
    console.log(`✓ ${month}: ${(stats.size / 1024).toFixed(0)} KB → ${target}`);
  } finally {
    await ctx.close();
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const ids = await listEditionIds(args.month);
  if (ids.length === 0) {
    console.error(args.month
      ? `Edition ${args.month} not found in site/src/content/editions/.`
      : 'No editions found in site/src/content/editions/.');
    process.exit(2);
  }

  const outDir = path.isAbsolute(args.output)
    ? args.output
    : path.join(PROJECT_ROOT, 'site', args.output);
  await mkdir(outDir, { recursive: true });
  console.log(`Output directory: ${outDir}`);

  await waitForServer(args.siteUrl, 20_000);

  const browser = await chromium.launch();
  const failures = [];
  try {
    for (const id of ids) {
      try {
        await generateOne(browser, args.siteUrl, id, outDir);
      } catch (err) {
        console.error(`✗ ${id} failed: ${err.message}`);
        failures.push({ id, err });
      }
    }
  } finally {
    await browser.close();
  }

  if (failures.length > 0) {
    console.error(`\n${failures.length} edition(s) failed:`);
    for (const f of failures) console.error(`  - ${f.id}: ${f.err.message}`);
    process.exit(1);
  }
  console.log(`\nGenerated ${ids.length} PDF(s) successfully.`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
