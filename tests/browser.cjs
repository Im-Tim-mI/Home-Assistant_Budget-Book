// Run against a disposable local backend, never a personal ledger.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('node:path');
const fs = require('node:fs');
const port = Number(process.env.BUDGET_BOOK_TEST_PORT || 18100);
const prefix = '/api/hassio_ingress/test-session/';
const root = path.resolve(__dirname, '..');

(async () => {
  // Emulate Supervisor's prefix stripping; reject escaped asset/API paths.
  const proxy = http.createServer((req, res) => {
    if (!req.url.startsWith(prefix)) { res.writeHead(404).end(); return; }
    const upstream = http.request({ hostname: '127.0.0.1', port, path: '/' + req.url.slice(prefix.length), method: req.method, headers: req.headers }, response => {
      res.writeHead(response.statusCode, response.headers);
      response.pipe(res);
    });
    upstream.on('error', () => res.writeHead(502).end());
    req.pipe(upstream);
  });
  await new Promise(resolve => proxy.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${proxy.address().port}${prefix}`;
  const browser = await chromium.launch({ channel: 'chrome' });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light', locale: 'zh-TW' });
    page.setDefaultTimeout(10000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', msg => { if (/Render error|Bootstrap fatal|bindEvents error/.test(msg.text())) errors.push(msg.text()); });
    page.on('response', response => { if (response.status() >= 400 && !response.url().endsWith('favicon.ico')) errors.push(response.status() + ' ' + response.url()); });
    page.on('dialog', dialog => dialog.accept());
    await page.goto(base);
    await page.locator('#main').waitFor({ state: 'visible' });
    const tab = name => { console.log('Tab:', name); return page.locator(`[data-tab="${name}"]`).click(); };
    const action = async (service, callback) => {
      const response = page.waitForResponse(r => r.url().endsWith('/' + service) && r.request().method() === 'POST');
      await callback();
      assert.equal((await response).status(), 200, service);
      console.log('Service:', service);
    };
    await tab('settings');
    await action('load_sample', () => page.locator('#btn-load-sample').click());
    await page.locator('#language-select').selectOption('zh-Hant');

    await page.locator('#btn-quick-add').click();
    await page.locator('#tx-amount').fill('321');
    await page.locator('#tx-note').fill('Port regression');
    await page.locator('#tx-cat-picker [data-cat="food"]').click();
    await action('add_transaction', () => page.locator('#tx-submit').click());
    await tab('tx');
    await page.locator('#tx-filter').fill('Port regression');
    await page.locator('#tx-filter').press('Tab');
    const row = page.locator('#tx-tbody tr').filter({ hasText: 'Port regression' });
    await row.locator('td').first().click();
    await page.locator('#modal-tx').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#tx-amount').inputValue(), '321');
    await page.locator('#tx-amount').fill('456');
    await action('update_transaction', () => page.locator('#tx-submit').click());
    await action('delete_transaction', () => row.locator('.del-btn').click());
    assert.equal(await page.locator('#modal-tx').isVisible(), false);

    await tab('categories');
    await page.locator('#btn-add-cat-expense').click();
    await page.locator('#cat-name').fill('Port category');
    await action('add_category', () => page.locator('#cat-submit').click());
    await tab('budgets');
    await page.locator('[data-budget-cat="port_category"]').click();
    await page.locator('#budget-amount').fill('1500');
    await action('set_budget', () => page.locator('#budget-submit').click());
    await tab('categories');
    await action('delete_category', () => page.locator('[data-del-cat="port_category"]').click());

    await tab('recurring');
    await page.locator('#btn-add-recurring').click();
    await page.locator('#rec-name').fill('Port subscription');
    await page.locator('#rec-amount').fill('99');
    await page.locator('#rec-day').fill('1');
    await action('add_recurring', () => page.locator('#rec-submit').click());
    await action('run_recurring', () => page.locator('#btn-run-recurring').click());

    await tab('settings');
    await page.locator('#btn-new-book').click();
    await page.locator('#book-name').fill('Port book');
    await action('create_book', () => page.locator('#book-submit').click());
    const bid = await page.locator('#book-switcher option').filter({ hasText: 'Port book' }).getAttribute('value');
    await action('set_active_book', () => page.locator('#book-switcher').selectOption(bid));
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#btn-export').click();
    const downloaded = await downloadPromise;
    const data = fs.readFileSync(await downloaded.path());
    await action('replace_data', () => page.locator('#import-file').setInputFiles({ name: 'backup.json', mimeType: 'application/json', buffer: data }));
    await action('load_sample', () => page.locator('#btn-load-sample').click());
    await page.reload();
    await page.locator('#main').waitFor({ state: 'visible' });

    const shell = await browser.newPage({ viewport: { width: 1000, height: 800 }, locale: 'zh-CN' });
    try {
      await shell.goto(base);
      await shell.setContent(`
        <home-assistant></home-assistant>
        <a id="sidebar-panel-budget_book" href="/budget_book">
          <ha-icon slot="start" icon="mdi:book-open-variant"></ha-icon>
          <span class="item-text" slot="headline">Budget Book</span>
        </a>
        <iframe id="budget-frame" src="${base}" style="width:800px;height:600px"></iframe>
        <script>
          document.querySelector('home-assistant').hass = {
            locale: { language: 'zh-CN' },
            panels: { budget_book: { url_path: 'budget_book', title: 'Budget Book', icon: 'mdi:book-open-variant' } }
          };
        </script>
      `);
      const frameElement = await shell.waitForSelector('#budget-frame');
      const frame = await frameElement.contentFrame();
      await frame.locator('#main').waitFor({ state: 'visible' });
      await shell.locator('#sidebar-panel-budget_book .item-text').waitFor({ hasText: '记账本' });
      assert.equal(await shell.locator('#sidebar-panel-budget_book ha-icon').getAttribute('icon'), 'mdi:notebook');
      await shell.evaluate(() => {
        document.querySelector('home-assistant').hass.locale.language = 'zh-TW';
      });
      await shell.locator('#sidebar-panel-budget_book .item-text').waitFor({ hasText: '記帳本', timeout: 5000 });
      console.log('PASS: parent Home Assistant sidebar title/icon follows Auto language.');
    } finally {
      await shell.close();
    }

    for (const lang of ['en', 'zh-Hant', 'zh-Hans']) {
      await tab('settings');
      await page.locator('#language-select').selectOption(lang);
      assert.equal(await page.locator('html').getAttribute('lang'), lang);
      for (const name of ['home', 'tx', 'charts', 'categories', 'budgets', 'recurring', 'settings']) {
        await tab(name);
        await page.locator(`#tab-${name}.active`).waitFor();
        if (name === 'charts') {
          await page.waitForTimeout(500);
          const nonblank = await page.locator('canvas').evaluateAll(canvases => canvases.every(c => {
            const rgba = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            return rgba.some((value, i) => i % 4 === 3 && value > 0);
          }));
          assert(nonblank, 'Charts must have rendered pixels');
        }
        await page.screenshot({ path: path.join(root, `docs/images/${lang}-${name}.png`) });
      }
      await page.setViewportSize({ width: 390, height: 844 });
      await tab('home');
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile overflow');
      await page.screenshot({ path: path.join(root, `docs/images/${lang}-mobile.png`) });
      await page.setViewportSize({ width: 1440, height: 1000 });
    }
    assert.deepEqual(errors, []);
    console.log('PASS: UI CRUD, filters, budget/category, recurring, books, JSON export/import, seven tabs x three languages, chart pixels, mobile layout, ingress-prefixed requests.');
  } catch (error) {
    console.error(error);
    throw error;
  } finally {
    await browser.close();
    proxy.closeAllConnections();
    await new Promise(resolve => proxy.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
