const {test, expect} = require('@playwright/test');
const fs = require('node:fs');

async function login(page, role) {
  if (role === 'public') return;
  await page.goto(role === 'admin' ? '/admin/login/' : '/accounts/login/');
  await page.locator('#id_username').fill(role === 'admin' ? 'browseradmin' : 'browserstudent');
  await page.locator('#id_password').fill('Browser-only-2026!');
  await Promise.all([
    page.waitForURL(url => !url.pathname.endsWith('/login/')),
    page.locator('button[type=submit],input[type=submit]').first().click(),
  ]);
}

async function layoutIssues(page) {
  return page.evaluate(() => {
    const issues = [];
    if (document.documentElement.scrollWidth > innerWidth + 1) issues.push('Document overflows');
    const header = document.querySelector('body.onedu-admin-workspace #header');
    if (header && header.getBoundingClientRect().height) {
      const boundary = header.getBoundingClientRect();
      for (const child of header.querySelectorAll('#site-name, #user-tools')) {
        const rect = child.getBoundingClientRect();
        if (rect.bottom > boundary.bottom + 2 || rect.right > innerWidth + 2) issues.push('Admin header clipped: ' + child.id);
      }
    }
    const cards = document.querySelector('#result_list.onedu-card-list');
    if (cards && cards.closest('.results').scrollWidth > cards.closest('.results').clientWidth + 1) issues.push('Card view requires horizontal scrolling');
    const root = document.querySelector('main') || document.querySelector('#content');
    for (const el of root.querySelectorAll('h1,h2,h3,p,span,strong,a,label,dt,dd,td,th,summary,button,input,select,textarea')) {
      const css = getComputedStyle(el), rect = el.getBoundingClientRect();
      if (!rect.width || !rect.height || css.visibility === 'hidden' || el.closest('.visually-hidden,.sr-only')) continue;
      let scrolling = false;
      for (let parent = el.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
        if (/^(auto|scroll)$/.test(getComputedStyle(parent).overflowX) && parent.scrollWidth > parent.clientWidth + 1) { scrolling = true; break; }
      }
      if (scrolling) continue;
      const label = el.tagName + '#' + el.id + '.' + String(el.className) + ' ' + el.textContent.slice(0, 60);
      if (rect.right > innerWidth + 2 || rect.left < -2) issues.push('Outside: ' + label);
      if (!/^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName) && el.scrollWidth > el.clientWidth + 2 && css.textOverflow !== 'ellipsis' && css.display !== 'inline' && Math.abs(parseFloat(css.textIndent) || 0) < 1000 && /\S/.test(el.textContent)) issues.push('Text clipped: ' + label);
    }
    return issues.slice(0, 15);
  });
}

test('home benefits crossfade in place on touch, keyboard and hover; account copy reports success and failure', async ({page, browser}) => {
  await page.goto('/');
  const benefit = page.locator('.portal-benefit').first();
  const before = await benefit.boundingBox();
  await benefit.tap();
  await expect(benefit).toHaveAttribute('aria-pressed', 'true');
  await expect(benefit.locator('.benefit-back')).toHaveCSS('opacity', '1');
  expect((await benefit.boundingBox()).height).toBe(before.height);
  expect(await layoutIssues(page)).toEqual([]);
  await benefit.press('Escape');
  await expect(benefit).toHaveAttribute('aria-pressed', 'false');
  await benefit.press('Enter');
  await expect(benefit.locator('.benefit-back')).toHaveCSS('opacity', '1');
  await benefit.tap();
  await expect(benefit.locator('.benefit-front')).toHaveCSS('opacity', '1');
  const desktop = await browser.newContext({viewport: {width: 1280, height: 900}, isMobile: false, hasTouch: false});
  try {
    const mousePage = await desktop.newPage();
    await mousePage.goto('http://127.0.0.1:8766/');
    const card = mousePage.locator('.portal-benefit').first();
    const originalHeight = (await card.boundingBox()).height;
    await card.hover();
    await expect(card.locator('.benefit-back')).toHaveCSS('opacity', '1');
    await expect(card.locator('.benefit-front')).toHaveCSS('opacity', '0');
    expect((await card.boundingBox()).height).toBe(originalHeight);
    expect(await card.locator('.benefit-back').evaluate(el => parseFloat(getComputedStyle(el).transitionDuration))).toBeGreaterThan(0);
    await mousePage.mouse.move(0, 0);
    await expect(card.locator('.benefit-front')).toHaveCSS('opacity', '1');
    await mousePage.emulateMedia({reducedMotion: 'reduce'});
    await expect(card.locator('.benefit-back')).toHaveCSS('transition-duration', '0s');
  } finally { await desktop.close(); }
  await login(page, 'student');
  await page.goto('/courses/browser-paid/');
  const copy = page.locator('[data-copy-account]');
  await page.evaluate(() => Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {writeText: async text => {window.copiedAccount = text;}}}));
  await copy.click();
  await expect(page.locator('[data-copy-status]')).toHaveText('계좌번호가 복사되었습니다.');
  expect(await page.evaluate(() => window.copiedAccount)).toBe(await copy.getAttribute('data-copy-account'));
  await page.evaluate(() => {
    navigator.clipboard.writeText = async () => {throw Error('Denied');};
    document.execCommand = () => false;
  });
  await copy.click();
  await expect(page.locator('[data-copy-status]')).toContainText('복사하지 못했습니다.');
  await expect(copy).toBeFocused();
  expect(await layoutIssues(page)).toEqual([]);
});

test('catalog leads through public conditions and login back to the classroom', async ({page}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/courses/');
  const card = page.locator('.catalog-card').filter({has: page.locator('a[href="/courses/browser-layout/"]')});
  await expect(card).toContainText('영상 차시');
  await expect(card).not.toContainText('이용료');
  await expect(card).not.toContainText('진도율');
  await expect(card.locator('form')).toHaveCount(0);
  await card.getByRole('link', {name: '상세 보기'}).click();
  await expect(page.locator('.detail-meta')).toContainText('이용료');
  await expect(page.locator('.detail-meta')).toContainText('승인 방식');
  await expect(page.locator('main')).not.toContainText('남은 기간');
  await expect(page.locator('[data-filter-incomplete]')).toHaveCount(0);
  await page.locator('#lessonSearch').fill('없는차시제목');
  await expect(page.locator('[data-filter-empty]')).toBeVisible();
  await page.locator('#lessonSearch').fill('');
  await expect(page.locator('[data-filter-item]').first()).toBeVisible();
  await page.getByRole('link', {name: '로그인 후 신청', exact: true}).click();
  await page.locator('#id_username').fill('browserstudent');
  await page.locator('#id_password').fill('Browser-only-2026!');
  await Promise.all([
    page.waitForURL('**/courses/browser-layout/'),
    page.locator('button[type=submit]').click(),
  ]);
  await expect(page.locator('main')).not.toContainText('진도율');
  await page.getByRole('link', {name: '내 강의실에서 보기', exact: true}).click();
  await expect(page.locator('main')).toContainText('전체 진도율');
  await expect(page.locator('main')).toContainText('남은 기간');
  expect(errors).toEqual([]);
});

for (const role of ['public', 'student', 'admin']) {
  for (const [width, height, scale] of [[320,740,100], [390,844,100], [412,915,100], [915,412,100], [390,844,200]]) {
    test(`${role} ${width}x${height} text ${scale}%`, async ({page}) => {
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.setViewportSize({width, height});
      await login(page, role);
      const routes = JSON.parse(fs.readFileSync('.browser-tests/routes.json', 'utf8'))[role];
      for (const route of routes) {
        await test.step(route, async () => {
          const response = await page.goto(route);
          expect(response.status()).toBe(200);
          // Redirects to login would make an authenticated audit meaningless.
          expect(new URL(page.url()).pathname).toBe(new URL(route, 'http://localhost').pathname);
          await page.evaluate(scale => document.documentElement.style.fontSize = scale + '%', scale);
          await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          expect(await layoutIssues(page)).toEqual([]);
          await page.evaluate(() => {
            document.documentElement.style.scrollBehavior = 'auto';
            scrollTo(0, document.documentElement.scrollHeight);
          });
          await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
          expect(await page.evaluate(() => {
            const nav = document.querySelector('.mobile-bottom-nav');
            return !nav || !nav.getBoundingClientRect().height || document.querySelector('main').getBoundingClientRect().bottom <= nav.getBoundingClientRect().top + 2;
          })).toBe(true);
        });
      }
      expect(errors).toEqual([]);
    });
  }
}

test('cards preserve editing, selection, rotation and table sorting', async ({page}) => {
  await login(page, 'admin');
  await page.goto('/admin/enrollments/enrollment/');
  await expect(page.locator('#result_list')).toHaveClass(/onedu-card-list/);
  const more = page.locator('.onedu-card-details-cell button').first();
  await more.click();
  await expect(more).toHaveAttribute('aria-expanded', 'true');
  const select = page.locator('#result_list select').first();
  await select.selectOption('requested');
  await page.getByRole('button', {name: '전체 선택', exact: true}).click();
  for (const checkbox of await page.locator('.action-select').all()) await expect(checkbox).toBeChecked();
  await page.getByRole('button', {name: /표 보기로 전환/}).click();
  await expect(page.locator('#result_list')).not.toHaveClass(/onedu-card-list/);
  await expect(select).toHaveValue('requested');
  await expect(page.locator('#result_list thead')).toBeVisible();
  await page.getByRole('button', {name: '카드 보기로 전환'}).click();
  await page.setViewportSize({width: 915, height: 412});
  expect(await layoutIssues(page)).toEqual([]);
  await page.setViewportSize({width: 1440, height: 900});
  await expect(page.locator('#result_list')).not.toHaveClass(/onedu-card-list/);
  await expect(select).toHaveValue('requested');
});

test('slow POST blocks duplicates and preserves the submitted action', async ({page}) => {
  test.setTimeout(30000);
  await login(page, 'admin');
  await page.goto('/admin/courses/course/add/');
  await page.locator('#id_title').fill('처리 표시 점검');
  await page.evaluate(() => {
    const frame = document.createElement('iframe');
    frame.name = 'submission-result';
    frame.hidden = true;
    document.body.append(frame);
    document.querySelector('#course_form').target = frame.name;
  });
  let posts = 0;
  let body;
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/admin/courses/course/add/', async route => {
    if (route.request().method() !== 'POST') return route.continue();
    posts++;
    body = route.request().postData();
    await gate;
    await route.fulfill({status: 200, contentType: 'text/html; charset=utf-8', body: '<p>접수 확인</p>'});
  });
  const submitter = page.locator('input[name=_continue]');
  try {
    await submitter.click({noWaitAfter: true});
    await expect(page.locator('form[aria-busy=true]')).toBeVisible();
    await expect(page.locator('.onedu-form-status')).toBeVisible();
    // Keyboard submission must also be rejected while the first request waits.
    await page.evaluate(() => document.querySelector('#course_form').requestSubmit());
    await page.waitForTimeout(100);
    expect(posts).toBe(1);
    expect(body).toContain('_continue');
  } finally { release(); }
  // BFCache restores must unlock the form instead of leaving a dead button.
  await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true})));
  await expect(page.locator('form[aria-busy=true]')).toHaveCount(0);
});

test('invalid submission stays editable and unsaved admin edits warn', async ({page}) => {
  test.setTimeout(30000);
  await login(page, 'admin');
  await page.goto('/admin/courses/course/add/');
  await page.locator('input[name=_save]').click();
  await expect(page.locator('.errornote')).toBeVisible();
  await expect(page.locator('form[aria-busy=true]')).toHaveCount(0);
  await page.locator('#id_title').fill('아직 저장하지 않은 강의');
  const dialog = page.waitForEvent('dialog', {timeout: 10000});
  const navigation = page.locator('#site-name a').click({noWaitAfter: true});
  const warning = await dialog;
  expect(warning.type()).toBe('beforeunload');
  await warning.dismiss();
  await expect(page.locator('#id_title')).toHaveValue('아직 저장하지 않은 강의');
  await navigation;
});

test('mobile forms and navigation work without JavaScript', async ({browser, baseURL}) => {
  const context = await browser.newContext({baseURL, javaScriptEnabled: false, viewport: {width: 320, height: 740}});
  const page = await context.newPage();
  await page.goto(baseURL + '/accounts/login/');
  await expect(page.locator('button[type=submit]').last()).toBeVisible();
  await login(page, 'admin');
  await page.goto('/admin/enrollments/enrollment/');
  await expect(page.locator('#result_list thead')).toBeVisible();
  await expect(page.locator('#result_list')).not.toHaveClass(/onedu-card-list/);
  await context.close();
});

test('cancelled validation does not lock a form', async ({page}) => {
  await page.goto('/accounts/signup/');
  await page.evaluate(() => {
    const form = document.querySelector('main form');
    form.addEventListener('submit', event => event.preventDefault());
    form.dispatchEvent(new SubmitEvent('submit', {bubbles: true, cancelable: true}));
  });
  await expect(page.locator('form[aria-busy=true]')).toHaveCount(0);
});

test('permission chooser changes are protected and touchable', async ({page}) => {
  test.setTimeout(30000);
  await login(page, 'admin');
  await page.goto('/admin/auth/group/add/');
  const chooser = page.locator('.selector-chooser .selector-add');
  const box = await chooser.boundingBox();
  expect(box.width).toBeGreaterThanOrEqual(44);
  expect(box.height).toBeGreaterThanOrEqual(44);
  const firstValue = await page.locator('#id_permissions_from option').first().getAttribute('value');
  await page.locator('#id_permissions_from').selectOption(firstValue);
  await chooser.click();
  await expect(page.locator('#id_permissions_to option')).toHaveCount(1);
  const dialog = page.waitForEvent('dialog', {timeout: 10000});
  const navigation = page.locator('#site-name a').click({noWaitAfter: true});
  const warning = await dialog;
  expect(warning.type()).toBe('beforeunload');
  await warning.dismiss();
  await expect(page.locator('#id_permissions_to option')).toHaveCount(1);
  await navigation;
});
