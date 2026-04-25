#!/usr/bin/env node
/**
 * Local DX wrapper for `generate-pdfs.mjs`. Starts the Astro preview
 * server, generates all PDFs, then shuts the server down. Used by the
 * `pdf:all` npm script in `site/package.json`.
 *
 * Assumes `astro build` has already produced `site/dist/`. The CI
 * pipeline calls `generate-pdfs.mjs` directly with its own server,
 * skipping this wrapper.
 */
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// Script lives at site/scripts/run-pdfs.mjs, so site/ is one up and the
// repo root is two up.
const SITE_DIR = path.resolve(__dirname, '..');
const PROJECT_ROOT = path.resolve(SITE_DIR, '..');
const PORT = 4327; // out of the way of the dev server (4321)
const SITE_URL = `http://127.0.0.1:${PORT}`;

function startPreview() {
  const child = spawn(
    'npx',
    ['astro', 'preview', '--host', '127.0.0.1', '--port', String(PORT)],
    { cwd: SITE_DIR, stdio: ['ignore', 'pipe', 'inherit'] },
  );
  child.stdout.on('data', (chunk) => process.stdout.write(`[astro] ${chunk}`));
  return child;
}

async function runGenerator() {
  return new Promise((resolve, reject) => {
    const child = spawn(
      'node',
      [path.join(__dirname, 'generate-pdfs.mjs'), '--site-url', SITE_URL, '--output', 'public/downloads'],
      { stdio: 'inherit' },
    );
    child.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(`generator exit ${code}`))));
  });
}

async function main() {
  const preview = startPreview();
  try {
    await runGenerator();
  } finally {
    preview.kill('SIGTERM');
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
