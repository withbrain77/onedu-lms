const {test, expect} = require('@playwright/test');
const fs = require('node:fs');
const http = require('node:http');

// Generated 60-second, silent solid-color H.264 fixture (160x90, 2 fps).
const media = fs.readFileSync('tests/browser/fixtures/seek.mp4');
let mediaServer, mediaUrl;
test.beforeAll(async () => {
  // Native WebKit media requests bypass Playwright route interception.
  mediaServer = http.createServer((request, response) => {
    const match = /^bytes=(\d+)-(\d*)$/.exec(request.headers.range || '');
    const start = match ? Number(match[1]) : 0;
    const end = match && match[2] ? Math.min(Number(match[2]), media.length - 1) : media.length - 1;
    response.writeHead(match ? 206 : 200, {'Content-Type': 'video/mp4', 'Accept-Ranges': 'bytes',
      'Content-Length': end - start + 1,
      ...(match ? {'Content-Range': `bytes ${start}-${end}/${media.length}`} : {})});
    response.end(media.subarray(start, end + 1));
  });
  await new Promise(resolve => mediaServer.listen(0, '127.0.0.1', resolve));
  mediaUrl = `http://127.0.0.1:${mediaServer.address().port}/seek.mp4`;
});
test.afterAll(async () => {
  mediaServer.closeAllConnections();
  await new Promise(resolve => mediaServer.close(resolve));
});

async function player(page, width = 390, height = 844) {
  await page.setViewportSize({width, height});
  await page.goto('/accounts/login/');
  // Use the actual player markup, stripping only server template tags and sources.
  const template = fs.readFileSync('templates/lessons/detail.html', 'utf8');
  const markup = template.slice(template.indexOf('<div id="videoPlayerShell"'), template.indexOf('<div class="empty-state video-empty">'))
    .replace(/{%[\s\S]*?%}/g, '').replace(/{{[\s\S]*?}}/g, '').replace(/<source[^>]*>/g, '');
  await page.setContent(`<meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0}</style>${markup}<div id="lessonEndActions" hidden></div>`);
  await page.addStyleTag({path: 'static/css/app.css'});
  await page.evaluate(async src => {
    const video = document.getElementById('lessonVideo');
    video.dataset.startPosition = '0';
    video.dataset.progressUrl = '/test-progress/';
    video.dataset.enrollmentId = 'test';
    window.seekTestSaves = [];
    window.oneduProgressSync = {resume: () => null, flush() {}, enqueue: item => window.seekTestSaves.push(item.payload)};
    video.muted = true;
    video.src = src;
    video.load();
    await video.play();
    video.pause();
  }, mediaUrl);
  await expect.poll(() => page.locator('video').evaluate(v => v.readyState)).toBeGreaterThan(0);
  await page.addScriptTag({path: 'static/js/video_progress.js'});
  await position(page, 25);
}

async function position(page, seconds) {
  await page.locator('video').evaluate((v, value) => { v.pause(); v.currentTime = value; }, seconds);
  await expect.poll(() => page.locator('video').evaluate(v => v.seeking)).toBe(false);
}
async function points(page) {
  const rect = await page.locator('#videoPlayerShell').boundingBox();
  return {left: {x: rect.x + rect.width * .2, y: rect.y + rect.height * .35},
    right: {x: rect.x + rect.width * .8, y: rect.y + rect.height * .35}};
}
async function tapPair(page, point) {
  await page.touchscreen.tap(point.x, point.y);
  await page.touchscreen.tap(point.x, point.y);
}
async function time(page, expected) {
  await expect.poll(() => page.locator('video').evaluate(v => v.currentTime)).toBeCloseTo(expected, 0);
}

async function startPlayback(page) {
  const before = await page.locator('video').evaluate(v => v.currentTime);
  // WebKit/GStreamer can resolve a repeated play() promise only at the end of
  // this silent clip after seeks. Verify the media clock, rather than waiting
  // for that promise and accidentally letting the clip finish before tapping.
  await page.locator('video').evaluate(v => {
    window.seekTestPlayError = null;
    v.play().catch(error => { window.seekTestPlayError = error.name; });
  });
  await expect(page.locator('video')).toHaveJSProperty('paused', false);
  await expect.poll(() => page.locator('video').evaluate(v => v.currentTime)).toBeGreaterThan(before);
  expect(await page.evaluate(() => window.seekTestPlayError)).toBeNull();
}

test('video side double taps seek exactly ten seconds, repeat and clamp at boundaries', async ({page}) => {
  await player(page);
  let p = await points(page);
  await tapPair(page, p.right); await time(page, 35);
  await expect(page.locator('#videoSeekFeedback')).toHaveText('10초 앞으로');
  await tapPair(page, p.right); await time(page, 45);
  await tapPair(page, p.left); await time(page, 35);
  await expect(page.locator('#videoSeekFeedback')).toHaveText('10초 뒤로');
  await expect(page.locator('#videoZoomReset')).toHaveText('100%');
  await position(page, 4); await tapPair(page, p.left); await time(page, 0);
  await position(page, 56); await tapPair(page, p.right); await time(page, 60);
  await page.setViewportSize({width: 844, height: 390});
  await position(page, 25); p = await points(page);
  await tapPair(page, p.right); await time(page, 35);
  await expect(page.locator('video')).toHaveJSProperty('paused', true);
  await page.screenshot({path: test.info().outputPath('seek-landscape.png')});
  await position(page, 25);
  await startPlayback(page);
  await tapPair(page, p.right);
  await expect(page.locator('video')).toHaveJSProperty('paused', false);
  expect(await page.locator('video').evaluate(v => v.currentTime)).toBeGreaterThanOrEqual(35);
});

test('desktop double clicks seek without fullscreen or zoom and preserve playing', async ({browser}) => {
  const context = await browser.newContext({baseURL: 'http://127.0.0.1:8766', isMobile: false, hasTouch: false});
  const page = await context.newPage();
  try {
  await player(page, 1200, 800);
  const p = await points(page);
  await page.mouse.dblclick(p.right.x, p.right.y); await time(page, 35);
  await page.mouse.dblclick(p.left.x, p.left.y); await time(page, 25);
  expect(await page.evaluate(() => Boolean(document.fullscreenElement))).toBe(false);
  await expect(page.locator('#videoZoomReset')).toHaveText('100%');
  await startPlayback(page);
  await page.mouse.dblclick(p.right.x, p.right.y);
  await expect(page.locator('video')).toHaveJSProperty('paused', false);
  expect(await page.locator('video').evaluate(v => v.currentTime)).toBeGreaterThanOrEqual(35);
  await page.locator('video').evaluate(v => v.pause());
  await expect.poll(() => page.evaluate(() => window.seekTestSaves.length)).toBeGreaterThan(0);
  const saves = await page.evaluate(() => window.seekTestSaves);
  expect(saves.length).toBeGreaterThan(0);
  expect(saves.reduce((sum, item) => sum + item.watched_increment_seconds, 0)).toBeLessThan(5);
  if (browser.browserType().name() === 'chromium') {
    await page.locator('#videoFullscreenButton').click();
    await expect.poll(() => page.evaluate(() => document.fullscreenElement?.id)).toBe('videoPlayerShell');
    await position(page, 25);
    const fullscreenPoints = await points(page);
    await page.mouse.dblclick(fullscreenPoints.left.x, fullscreenPoints.left.y);
    await time(page, 15);
    await page.locator('#videoFullscreenButton').click();
    await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(false);
  }
  } finally { await context.close(); }
});

test('single taps, controls, cancelled touches and drags do not trigger seeking', async ({page}) => {
  await player(page);
  const p = await points(page);
  await page.touchscreen.tap(p.left.x, p.left.y); await time(page, 25);
  await page.touchscreen.tap(p.right.x, p.right.y); await time(page, 25);
  await page.locator('#videoZoomToggle').tap();
  await page.locator('[data-zoom-action="in"]').tap();
  await page.locator('[data-zoom-action="in"]').tap();
  await time(page, 25);
  await expect(page.locator('#videoZoomReset')).toHaveText('150%');
  await page.locator('[data-zoom-action="reset"]').tap();
  await page.locator('#videoZoomToggle').tap();
  await page.locator('video').dispatchEvent('touchcancel');
  await page.touchscreen.tap(p.left.x, p.left.y); await time(page, 25);
  await page.locator('video').dispatchEvent('touchcancel');
  await page.locator('video').evaluate((v, point) => {
    const touch = (x, y) => ({identifier: 1, target: v, clientX: x, clientY: y});
    const start = touch(point.x, point.y), end = touch(point.x + 60, point.y);
    for (const [name, touches, changedTouches] of [
      ['touchstart', [start], [start]], ['touchmove', [end], [end]], ['touchend', [], [end]],
    ]) {
      const event = new Event(name, {bubbles: true, cancelable: true});
      Object.defineProperties(event, {touches: {value: touches}, changedTouches: {value: changedTouches}});
      v.dispatchEvent(event);
    }
  }, p.left);
  await page.touchscreen.tap(p.left.x, p.left.y); await time(page, 25);
});
