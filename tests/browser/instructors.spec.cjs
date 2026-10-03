const {test, expect} = require('@playwright/test');
const fs = require('fs');

test('admin can grant, calculate, pay, refund and close a revoked instructor agreement', async ({page, browser}, testInfo) => {
  const fixture = JSON.parse(fs.readFileSync('.browser-tests/instructor-workflows.json', 'utf8'))[testInfo.project.name];
  const login = async (target, username) => {
    await target.goto('/accounts/login/');
    await target.locator('#id_username').fill(username);
    await target.locator('#id_password').fill('Browser-only-2026!');
    await Promise.all([target.waitForURL(url => !url.pathname.endsWith('/login/')), target.locator('button[type=submit]').click()]);
  };
  const save = async (path) => {
    await Promise.all([page.waitForURL(url => url.pathname === path), page.locator('input[name="_save"]').first().click()]);
  };
  const action = async (name) => {
    await page.locator('input.action-select').first().check();
    await page.locator('select[name="action"]').first().selectOption(name);
    await Promise.all([page.waitForNavigation(), page.locator('button[name="index"]').first().click()]);
    await expect(page.locator('.messagelist .error')).toHaveCount(0);
  };
  await login(page, 'browseradmin');
  const userUrl = `/admin/accounts/user/${fixture.teacher_id}/change/`;
  await page.goto(userUrl);
  await expect(page.locator('#id_is_instructor')).not.toBeChecked();
  await page.locator('#id_is_instructor').check();
  await save('/admin/accounts/user/');
  await page.goto(`/admin/instructors/teachingassignment/add/?instructor=${fixture.teacher_id}&course=${fixture.course_id}&lesson=${fixture.lesson_id}`);
  await page.locator('#id_method').selectOption('percent');
  await page.locator('#id_allocation_percent').fill('50');
  await page.locator('#id_royalty_percent').fill('40');
  await page.locator('#id_starts_on').fill(fixture.today);
  await save('/admin/instructors/teachingassignment/');
  await page.goto(`/admin/instructors/teachingassignment/?q=${fixture.username}`);
  const assignmentUrl = await page.locator('#result_list tbody th a').first().getAttribute('href');
  await page.goto(`/admin/instructors/revenuerecord/${fixture.revenue_id}/change/`);
  await page.locator('#id_amount').fill('30000');
  await page.locator('#id_received_on').fill(fixture.today);
  await save('/admin/instructors/revenuerecord/');
  await page.goto(`/admin/instructors/revenuerecord/?id__exact=${fixture.revenue_id}`);
  await action('verify_and_calculate');
  const context = await browser.newContext({baseURL: 'http://127.0.0.1:8766', viewport: {width: 390, height: 844}});
  const teacher = await context.newPage();
  try {
    await login(teacher, fixture.username);
    await teacher.goto('/instructor/');
    await expect(teacher.locator('.instructor-ledger')).toContainText('6,000원');
    await page.goto(`/admin/instructors/instructorearning/?instructor__id__exact=${fixture.teacher_id}`);
    await action('confirm_earnings');
    await action('mark_paid');
    await teacher.reload();
    await expect(teacher.locator('.instructor-ledger')).toContainText('지급 완료');
    await page.goto(`/admin/instructors/refundrecord/add/?revenue=${fixture.revenue_id}`);
    await page.locator('#id_amount').fill('15000');
    await page.locator('#id_refunded_on').fill(fixture.today);
    await page.locator('#id_reason').fill('가상 환경 부분 환불 점검');
    await save('/admin/instructors/refundrecord/');
    await page.goto(`/admin/instructors/refundrecord/?revenue__id__exact=${fixture.revenue_id}`);
    await action('apply_refunds');
    await teacher.reload();
    await expect(teacher.locator('.instructor-ledger')).toContainText('-3,000원');
    await expect(teacher.locator('.instructor-ledger')).toContainText('6,000원');
    await teacher.screenshot({path: testInfo.outputPath('instructor-refund.png'), fullPage: true});
    await page.goto(userUrl);
    await page.locator('#id_is_instructor').uncheck();
    await save('/admin/accounts/user/');
    expect((await teacher.goto('/instructor/')).status()).toBe(403);
    expect((await teacher.request.get('/instructor/?download=csv')).status()).toBe(403);
    expect((await teacher.goto('/classroom/')).status()).toBe(200);
    await page.goto(assignmentUrl);
    await expect(page.locator('#id_instructor')).toHaveCount(0);
    await page.locator('#id_ends_on').fill(fixture.today);
    await save('/admin/instructors/teachingassignment/');
    await page.goto(assignmentUrl);
    await expect(page.locator('#id_ends_on')).toHaveValue(fixture.today);
  } finally {
    await context.close();
  }
});

test('instructor can view own ledger, export and continue as student at mobile and desktop sizes', async ({page}, testInfo) => {
  await page.goto('/accounts/login/');
  await page.locator('#id_username').fill('browserinstructor');
  await page.locator('#id_password').fill('Browser-only-2026!');
  await Promise.all([
    page.waitForURL(url => !url.pathname.endsWith('/login/')),
    page.locator('button[type=submit]').click(),
  ]);
  await page.goto('/instructor/');
  await expect(page.getByRole('heading', {name: '강사실', exact: true})).toBeVisible();
  await expect(page.locator('.instructor-ledger')).toContainText('10,000원');
  for (const size of [{width: 320, height: 740}, {width: 390, height: 844}, {width: 844, height: 390}, {width: 1280, height: 900}]) {
    await page.setViewportSize(size);
    const issues = await page.evaluate(() => {
      const out = [];
      if (document.documentElement.scrollWidth > innerWidth + 1) out.push('page overflows');
      for (const el of document.querySelectorAll('.instructor-dashboard strong,.instructor-dashboard p,.instructor-dashboard dd,.instructor-dashboard input,.instructor-dashboard h3')) {
        const rect = el.getBoundingClientRect();
        if (rect.right > innerWidth + 1 || rect.left < 0) out.push(el.textContent);
        if (getComputedStyle(el).display !== 'inline' && el.scrollWidth > el.clientWidth + 2) out.push('clipped: '+el.textContent);
      }
      return out;
    });
    expect(issues).toEqual([]);
  }
  await page.setViewportSize({width: 390, height: 844});
  await page.screenshot({path: testInfo.outputPath('instructor-mobile.png'), fullPage: true});
  const exportLink = page.getByRole('link', {name: '정산 내역 내려받기 (CSV·엑셀용)'});
  const csv = await page.request.get(await exportLink.evaluate(el => el.href));
  expect(csv.ok()).toBe(true);
  expect(csv.headers()['content-type']).toContain('text/csv');
  expect(await csv.text()).toContain('10000');
  await page.getByRole('link', {name: '수강 중인 내 강의실'}).click();
  await expect(page).toHaveURL(/\/classroom\//);
  await page.goto('/accounts/profile/');
  await page.getByRole('link', {name: '강사실 보기'}).click();
  await expect(page).toHaveURL(/\/instructor\//);
});
