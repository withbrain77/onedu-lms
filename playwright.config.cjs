const {defineConfig} = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests/browser',
  timeout: 180000,
  expect: {timeout: 10000},
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', {open: 'never'}]],
  use: {baseURL: 'http://127.0.0.1:8766', trace: 'retain-on-failure', screenshot: 'only-on-failure'},
  webServer: {command: 'python tests/browser/start_server.py', url: 'http://127.0.0.1:8766/accounts/login/', reuseExistingServer: false, timeout: 120000, stderr: 'ignore'},
  projects: [
    {name: 'android-chromium', use: {browserName: 'chromium', viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true}},
    {name: 'iphone-webkit', use: {browserName: 'webkit', viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true}},
  ],
});
