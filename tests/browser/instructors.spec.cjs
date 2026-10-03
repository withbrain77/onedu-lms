const {test, expect} = require('@playwright/test');

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
