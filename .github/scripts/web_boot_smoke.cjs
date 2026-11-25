/* FleetLuma FL-22: unauthenticated first-frame and recovery smoke.
 * Runs against the CI-built Web files on loopback, never a production account.
 */
'use strict';

const path = require('node:path');
const fs = require('node:fs/promises');
const { chromium, firefox } = require(
  path.resolve(process.cwd(), '.ci-browser/node_modules/playwright')
);

const BASE_URL = process.env.FLEETLUMA_SMOKE_URL || 'http://127.0.0.1:8088/';
const ARTIFACTS = path.resolve(process.cwd(), 'test-results/web-startup');

async function capture(page, browserName, iteration, error, events) {
  await fs.mkdir(ARTIFACTS, { recursive: true });
  const prefix = `${browserName}-${iteration}`;
  await Promise.allSettled([
    page.screenshot({ path: path.join(ARTIFACTS, `${prefix}.png`), fullPage: true }),
    fs.writeFile(path.join(ARTIFACTS, `${prefix}.json`),
      JSON.stringify({
        browser: browserName,
        attempt: iteration,
        error: String(error),
        events: events.slice(-30),
        url: page.url(),
      }, null, 2)),
  ]);
}

async function checkFirstFrame(browser, name, iteration) {
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    serviceWorkers: 'block',
  });
  const page = await context.newPage();
  const events = [];
  await context.addInitScript(() => {
    window.__fleetlumaFirstFrameObserved = false;
    window.addEventListener('flutter-first-frame', () => {
      window.__fleetlumaFirstFrameObserved = true;
    }, { once: true });
  });
  page.on('pageerror', e => events.push({ type: 'pageerror', error: String(e).slice(0, 240) }));
  page.on('response', r => {
    if (/\.(?:js|wasm)$/.test(new URL(r.url()).pathname) && r.status() >= 400) {
      events.push({ type: 'asset', status: r.status(), path: new URL(r.url()).pathname });
    }
  });
  try {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.waitForFunction(() =>
      window.__fleetlumaFirstFrameObserved === true &&
      document.getElementById('fleetluma-boot')?.hidden === true &&
      document.querySelector('flutter-view, flt-glass-pane') !== null,
      null, { timeout: 45000 }
    );
    if (events.some(e => e.type === 'pageerror' || e.type === 'asset')) {
      throw new Error('Startup Javascript or runtime asset error');
    }
    if (iteration === 1) {
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() =>
        document.getElementById('fleetluma-boot')?.hidden === true &&
        document.querySelector('flutter-view, flt-glass-pane') !== null,
        null, { timeout: 45000 });
    }
    process.stdout.write(`PASS ${name} cold start ${iteration}/5 + first frame\n`);
  } catch (error) {
    await capture(page, name, iteration, error, events);
    throw error;
  } finally {
    await context.close();
  }
}

async function checkScriptRecovery(browser, name) {
  const context = await browser.newContext({ serviceWorkers: 'block' });
  const page = await context.newPage();
  try {
    await page.route('**/flutter_bootstrap.js', route =>
      route.fulfill({ status: 404, body: 'not found', contentType: 'text/plain' }));
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 20000 });
    await page.locator('#fleetluma-retry').waitFor({ state: 'visible', timeout: 10000 });
    const text = await page.locator('#fleetluma-status').textContent();
    if (!text?.includes('could not finish loading')) {
      throw new Error('Missing visible startup recovery guidance');
    }
    process.stdout.write(`PASS ${name} failed script displays recovery instead of white page\n`);
  } catch (error) {
    await capture(page, name, 'broken-bootstrap', error, []);
    throw error;
  } finally {
    await context.close();
  }
}

(async () => {
  await fs.mkdir(ARTIFACTS, { recursive: true });
  for (const [name, launcher] of [['chromium', chromium], ['firefox', firefox]]) {
    const browser = await launcher.launch({ headless: true });
    try {
      for (let attempt = 1; attempt <= 5; attempt++) {
        await checkFirstFrame(browser, name, attempt);
      }
      await checkScriptRecovery(browser, name);
    } finally {
      await browser.close();
    }
  }
  console.log('PASS: 10 fresh Chromium/Firefox loads, reloads, and broken-bootstrap recovery');
})().catch(error => {
  console.error('FL-22 browser startup regression FAILED:', error.message);
  process.exitCode = 1;
});
