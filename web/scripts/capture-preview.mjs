import {chromium} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ryde-demo-preview-'));
const environment = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith('RYDE_')));
environment.RYDE_CONFIG = path.join(directory, 'missing-config.json');
execFileSync('uv', ['run', '--project', '..', 'python', '../scripts/create_demo_dataset.py', '--output', directory], {env: environment});
const dashboard = JSON.parse(execFileSync('uv', ['run', '--project', '..', 'ryde', 'stats', '--no-fetch', '--no-open', '--data-dir', directory, '--ttl', '300'], {env: environment, encoding: 'utf8'}));
let browser;
try {
  browser = await chromium.launch();
  const page = await browser.newPage({viewport: {width: 1600, height: 1120}, deviceScaleFactor: 1});
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  await page.goto(dashboard.url);
  await page.locator('.metrics div').first().locator('b').filter({hasText: '180'}).waitFor();
  await page.waitForTimeout(8000);
  if (errors.length) throw new Error(errors.join('\n'));
  await page.screenshot({path: '../docs/assets/dashboard.png', fullPage: true});
  console.log('Captured dashboard preview using 180 generated demo rides.');
} finally {
  await browser?.close();
  execFileSync('uv', ['run', '--project', '..', 'ryde', 'stats', '--stop', dashboard.url], {env: environment});
  fs.rmSync(directory, {recursive: true, force: true});
}
