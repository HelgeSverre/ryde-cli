import {expect, test} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// Explicitly synthetic fixtures, served by interception. No Ryde account or
// public tile service is contacted by these browser tests.
const rides = [
  {useId: 'synthetic-1', startTime: '2026-01-05 08:00:00', endTime: '2026-01-05 08:10:00', startGps: '10,20', endGps: '10.01,20.01', paidNum: 2000, useDist: 1000, startAdd: 'Synthetic origin'},
  {useId: 'synthetic-2', startTime: '2026-01-06 09:00:00', endTime: '2026-01-06 09:15:00', startGps: '10.01,20.01', endGps: '10,20', paidNum: 3000, useDist: 1500, startAdd: 'Synthetic destination'},
  {useId: 'synthetic-3', startTime: '2026-01-10 10:00:00', endTime: '2026-01-10 10:20:00', startGps: '10,20', endGps: '10.02,20.02', paidNum: 4000, useDist: 2000},
];
const manifest = {version: 1, exportedAt: '2026-01-11T00:00:00Z', rideFile: 'rides.json', routeFiles: [{year: '2026', file: 'routes.json', count: 1}], counts: {rides: 3, complete: 1, missing: 0, failed: 0}};

test('loads synthetic data, filters routes and survives a token-prefixed URL', async ({page}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('https://**/*', async (route) => {
    if (route.request().url().includes('openfreemap.org/styles/')) {
      await route.fulfill({json: {version: 8, sources: {}, layers: []}});
    } else {
      await route.abort();
    }
  });
  await page.route('**/data/**', async (route) => {
    const file = new URL(route.request().url()).pathname.split('/').pop();
    const json = file === 'manifest.json' ? manifest : file === 'rides.json' ? {rides} : {routes: {'synthetic-1': {status: 'complete', response: {locus: [{gpsAddress: '10,20'}, {gpsAddress: '10.01,20.01'}]}}}};
    await route.fulfill({json});
  });
  await page.goto('/synthetic-session/');
  const rideCount = page.locator('.metrics div').first().locator('b');
  await expect(rideCount).toHaveText('3');
  await page.getByLabel('Route detail').selectOption('trace');
  await expect(rideCount).toHaveText('1');
  await page.getByLabel('Route detail').selectOption('fallback');
  await expect(rideCount).toHaveText('2');
  await page.getByLabel('Route detail').selectOption('all');
  await page.getByLabel('Ride type').selectOption('weekend');
  await expect(rideCount).toHaveText('1');
  expect(errors).toEqual([]);
});

test('bundled dashboard loads through the real CLI server and privacy headers', async ({page}) => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ryde-synthetic-browser-'));
  for (const [name, value] of Object.entries({'manifest.json': {...manifest, routeFiles: [], counts: {...manifest.counts, complete: 0}}, 'rides.json': {rides}})) {
    fs.writeFileSync(path.join(directory, name), JSON.stringify(value), {mode: 0o600});
  }
  const environment = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith('RYDE_')));
  environment.RYDE_CONFIG = path.join(directory, 'missing-config.json');
  const result = JSON.parse(execFileSync('uv', ['run', '--project', '..', 'ryde', 'stats', '--no-fetch', '--no-open', '--data-dir', directory, '--ttl', '30'], {env: environment, encoding: 'utf8'}));
  try {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.route('https://**/*', async (route) => {
      if (route.request().url().includes('openfreemap.org/styles/')) await route.fulfill({json: {version: 8, sources: {}, layers: []}});
      else await route.abort();
    });
    const response = await page.goto(result.url);
    expect(response?.headers()['referrer-policy']).toBe('no-referrer');
    await expect(page.locator('.metrics div').first().locator('b')).toHaveText('3');
    await expect(page.locator('canvas').first()).toBeVisible();
    expect(errors).toEqual([]);
  } finally {
    execFileSync('uv', ['run', '--project', '..', 'ryde', 'stats', '--stop', result.url], {env: environment, encoding: 'utf8'});
    fs.rmSync(directory, {recursive: true, force: true});
  }
});
