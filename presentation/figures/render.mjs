import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, 'output');
const port = 4173;
const baseUrl = `http://127.0.0.1:${port}`;
const pages = process.argv.slice(2).length ? process.argv.slice(2) : ['06', '14'];

function waitForServer(url, timeoutMs = 30000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const res = await fetch(url);
        if (res.ok) return resolve();
      } catch {}
      if (Date.now() - started > timeoutMs) return reject(new Error(`Timed out waiting for ${url}`));
      setTimeout(check, 300);
    };
    check();
  });
}

const server = spawn('npx', ['vite', '--host', '127.0.0.1', '--port', String(port)], {
  cwd: __dirname,
  stdio: ['ignore', 'pipe', 'pipe'],
});

server.stdout.on('data', (data) => process.stdout.write(data));
server.stderr.on('data', (data) => process.stderr.write(data));

try {
  await mkdir(outDir, { recursive: true });
  await waitForServer(baseUrl);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });

  for (const pageId of pages) {
    const url = `${baseUrl}/?page=${pageId}`;
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.screenshot({ path: path.join(outDir, `page-${pageId}.png`), fullPage: false });
    console.log(`rendered output/page-${pageId}.png`);
  }

  await browser.close();
} finally {
  server.kill('SIGTERM');
}
