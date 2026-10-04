// Run with Playwright installed: node tests/test_sources_ui.cjs
// Optional: BROWSER_EXECUTABLE_PATH, UI_SCREENSHOT_DIR.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.BROWSER_EXECUTABLE_PATH ? { executablePath: process.env.BROWSER_EXECUTABLE_PATH } : {}),
  });
  try {
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      const quote = 'Die zwei Komponenten brauchen wir nämlich, um dieses String Design durchführen zu können. Da gucken wir rein, wo kriegen wir die Kenngrößen eigentlich immer her im realen Projektgeschäft. Weil wir dann alles zusammen gesammelt haben, führen wir das in einem schönen String Design Beispiel durch.';
      let sources = [{
        subject_area_number: '1', subject_area_name: 'Komponenten der Photovoltaik',
        module_number: '01', module_name: 'Stringdesign', video_number: '0', video_name: 'Intro',
        time_range: '(0:01:28 - 0:01:46)', text: quote,
      }];
      const headers = [];
      let sourcesRequests = 0;
      await page.route('http://chatbot.test/**', route => {
        const url = new URL(route.request().url());
        const files = { '/': ['index.html', 'text/html'], '/app.js': ['app.js', 'text/javascript'], '/style.css': ['style.css', 'text/css'] };
        if (files[url.pathname]) {
          const [file, contentType] = files[url.pathname];
          return route.fulfill({ contentType, body: fs.readFileSync(path.join(__dirname, '../frontend', file), 'utf8') });
        }
        let result;
        if (url.pathname === '/health') result = { status: 'ok' };
        else if (url.pathname === '/videos') result = [];
        else if (url.pathname === '/chat') {
          headers.push(route.request().headers()['x-conversation-id']);
          result = { conversation_id: 'test-session', answer: quote, citations: sources, sources };
        }
        else if (url.pathname === '/sources') {
          sourcesRequests += 1;
          result = []; // Regression: later lookup has lost the server-side context.
        } else return route.fulfill({ status: 404, body: '{}' });
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify(result) });
      });
      await page.goto('http://chatbot.test/');
      await page.locator('#chat-input').fill('Stringdesign');
      await page.locator('#send-btn').click();
      await page.locator('.message.bot .bubble').filter({ hasText: quote }).waitFor();
      await page.locator('#show-sources-btn').click();
      await page.locator('.source-card').waitFor({ timeout: 3000 });
      assert.equal(await page.locator('.source-quote').textContent(), quote);
      assert.match(await page.locator('.source-area').textContent(), /Fachbereich 1 · Komponenten/);
      assert.equal(await page.locator('.source-time').textContent(), 'Zeitstelle: (0:01:28 - 0:01:46)');
      assert.equal(sourcesRequests, 0);
      assert.equal(headers[0], undefined);
      assert.doesNotMatch(await page.locator('#dialog-body').textContent(), /Relevanz/);
      const layout = await page.evaluate(() => {
        const dialog = document.querySelector('#info-dialog');
        const body = document.querySelector('#dialog-body');
        const card = document.querySelector('.source-card');
        const r = dialog.getBoundingClientRect();
        return { left: r.left, right: r.right, top: r.top, bottom: r.bottom,
          overflow: body.scrollWidth > body.clientWidth, height: card.getBoundingClientRect().height,
          whiteSpace: getComputedStyle(body).whiteSpace };
      });
      assert.equal(layout.whiteSpace, 'normal');
      assert.equal(layout.overflow, false);
      assert.ok(layout.left >= 0 && layout.right <= viewport.width);
      assert.ok(layout.top >= 0 && layout.bottom <= viewport.height);
      if (viewport.width > 1000) assert.ok(layout.height < 310, 'Source card must not have huge blank areas');
      if (process.env.UI_SCREENSHOT_DIR) {
        fs.mkdirSync(process.env.UI_SCREENSHOT_DIR, { recursive: true });
        await page.screenshot({ path: path.join(process.env.UI_SCREENSHOT_DIR, `sources-${viewport.width}.png`) });
      }
      await page.locator('#close-dialog-btn').click();
      sources = Array.from({ length: 12 }, () => ({ ...sources[0], text: quote + '\n<script>window.untrusted = true</script>' }));
      await page.evaluate(() => sendMessage('Weitere Quellen'));
      assert.equal(headers[1], 'test-session');
      await page.locator('#show-sources-btn').click();
      await page.waitForFunction(() => document.querySelectorAll('.source-card').length === 12);
      assert.equal(await page.locator('.source-card script').count(), 0);
      assert.equal(await page.evaluate(() => window.untrusted), undefined);
      assert.ok(await page.locator('#dialog-body').evaluate(el => el.scrollHeight > el.clientHeight));
      await page.locator('#dialog-body').evaluate(el => { el.scrollTop = el.scrollHeight; });
      await page.locator('#close-dialog-btn').click();
      sources = [];
      await page.evaluate(() => sendMessage('Danke'));
      await page.locator('#show-sources-btn').click();
      await page.locator('#dialog-body').filter({ hasText: 'keine zitierten Quellenstellen' }).waitFor();
      assert.equal(await page.locator('.source-card').count(), 0);
      assert.equal(sourcesRequests, 0);
      assert.deepEqual(errors, []);
      await page.close();
      console.log(`Sources UI passed: ${viewport.width}x${viewport.height}`);
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
