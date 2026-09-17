const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../static/js/video_recovery.js'), 'utf8');
const settle = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };

function player(options = {}) {
  const timers = new Map();
  let timerId = 0;
  const video = Object.assign(new EventTarget(), {
    dataset: {startPosition: '12', progressKey: '1-1-1', accessUrl: '/lessons/1/access/', loginUrl: '/accounts/login/', courseUrl: '/classroom/1/'},
    paused: true, currentTime: options.position || 12, duration: 120, readyState: options.readyState || 0, error: null,
    loads: 0, plays: 0,
    load() { this.loads++; },
    play() { this.plays++; this.paused = false; this.dispatchEvent(new Event('play')); return Promise.resolve(); },
    pause() { this.paused = true; this.dispatchEvent(new Event('pause')); },
    canPlayType() { return 'maybe'; },
  });
  const elements = {
    lessonVideo: video,
    playbackNotice: {hidden: true}, playbackNoticeText: {textContent: ''},
    videoRetryButton: Object.assign(new EventTarget(), {hidden: false, disabled: false}),
    playbackAccessLink: {hidden: true, href: ''},
  };
  const window = new EventTarget();
  const hlsInstances = [];
  class FakeHls {
    static isSupported() { return true; }
    static Events = {ERROR: 'error'};
    constructor() { hlsInstances.push(this); }
    on(_event, callback) { this.onError = callback; }
    loadSource(url) { this.url = url; }
    attachMedia(media) { this.video = media; }
    destroy() { this.destroyed = true; }
  }
  if (options.hls) { video.dataset.hlsUrl = '/lessons/1/hls/playlist.m3u8'; window.Hls = FakeHls; }
  const navigator = {onLine: true};
  let fetches = 0;
  let responseCode = options.code || 'allowed';
  vm.runInNewContext(source, {
    window, document: {getElementById: id => elements[id]}, navigator,
    location: {pathname: '/lessons/1/watch/', search: '?x=1'},
    Event, AbortController, Hls: FakeHls,
    setTimeout(callback, delay) { const id = ++timerId; timers.set(id, {callback, delay}); return id; },
    clearTimeout(id) { timers.delete(id); },
    async fetch() {
      fetches++;
      if (responseCode === 'network') throw new Error('offline');
      const status = responseCode === 'allowed' ? 200 : responseCode === 'login_required' ? 401 : 403;
      return {status, ok: status === 200, json: async () => ({ok: status === 200, code: responseCode})};
    },
  });
  return {
    video, window, elements, navigator, hlsInstances,
    get fetches() { return fetches; },
    setCode(code) { responseCode = code; },
    fail() { video.error = {code: 2}; video.dispatchEvent(new Event('error')); },
    async tick() {
      const timer = [...timers.entries()].sort((a, b) => a[1].delay - b[1].delay)[0];
      assert(timer, 'expected a pending retry');
      timers.delete(timer[0]); timer[1].callback(); await settle();
    },
    async manual() { elements.videoRetryButton.dispatchEvent(new Event('click')); await settle(); },
    get timerCount() { return timers.size; },
  };
}

test('fatal HLS failure rebuilds playback and restores position without changing progress', async () => {
  const p = player({hls: true});
  await p.video.play();
  p.video.currentTime = 37;
  p.video.dispatchEvent(new Event('timeupdate'));
  p.hlsInstances[0].onError(null, {fatal: true});
  await p.tick();
  assert.equal(p.fetches, 1);
  assert.equal(p.hlsInstances.length, 2);
  assert(p.hlsInstances[0].destroyed);
  p.video.currentTime = 0;
  p.video.dispatchEvent(new Event('loadedmetadata'));
  assert.equal(p.video.currentTime, 37);
  assert.equal(p.video.plays, 2);
});

test('native playback stops after three automatic retries and allows manual retry', async () => {
  const p = player();
  for (let i = 0; i < 3; i++) { p.fail(); await p.tick(); }
  p.fail();
  assert.equal(p.video.loads, 3);
  assert.equal(p.timerCount, 0);
  assert.equal(p.elements.videoRetryButton.hidden, false);
  await p.manual();
  assert.equal(p.video.loads, 4);
});

test('login expiry shows a return link and never retries protected media', async () => {
  const p = player({code: 'login_required'});
  p.fail(); await p.tick();
  assert.equal(p.video.loads, 0);
  assert.equal(p.elements.playbackAccessLink.href, '/accounts/login/?next=%2Flessons%2F1%2Fwatch%2F%3Fx%3D1');
  assert.equal(p.elements.playbackAccessLink.textContent, '다시 로그인');
  assert.equal(p.elements.videoRetryButton.hidden, true);
  assert.equal(p.timerCount, 0);
});

test('enrollment expiry offers reenrollment instead of login', async () => {
  const p = player({code: 'ended'});
  p.fail(); await p.tick();
  assert.equal(p.elements.playbackAccessLink.href, '/classroom/1/');
  assert.equal(p.elements.playbackAccessLink.textContent, '재수강 확인');
  assert.equal(p.video.loads, 0);
});

test('offline failure waits for online without spending retries', async () => {
  const p = player();
  p.navigator.onLine = false; p.fail();
  assert.equal(p.timerCount, 0);
  assert.equal(p.fetches, 0);
  p.navigator.onLine = true;
  p.window.dispatchEvent(new Event('online')); await settle();
  assert.equal(p.video.loads, 1);
});

test('failed access requests are retried with a finite limit', async () => {
  const p = player({code: 'network'});
  p.fail();
  for (let i = 0; i < 3; i++) await p.tick();
  assert.equal(p.fetches, 3);
  assert.equal(p.video.loads, 0);
  assert.equal(p.timerCount, 0);
});

test('progress-save denial pauses playback and displays the matching access action', () => {
  const p = player();
  p.window.dispatchEvent(new CustomEvent('onedu:progress-save', {detail: {key: '1-1-1', state: 'access', data: {code: 'ended'}}}));
  assert.equal(p.elements.playbackAccessLink.textContent, '재수강 확인');
  assert(p.video.paused);
});

test('autoplay rejection lets the next user gesture play without another reload', async () => {
  const p = player();
  await p.video.play();
  p.fail(); await p.tick();
  p.video.play = () => Promise.reject(new Error('NotAllowedError'));
  p.video.dispatchEvent(new Event('loadedmetadata'));
  await settle();
  let played = false;
  p.video.play = () => { played = true; return Promise.resolve(); };
  await p.manual();
  assert(played);
  assert.equal(p.video.loads, 1);
});

test('HLS attachment retains a position restored before the player script loaded', () => {
  const p = player({hls: true, readyState: 1, position: 37});
  p.video.currentTime = 0;
  p.video.dispatchEvent(new Event('loadedmetadata'));
  assert.equal(p.video.currentTime, 37);
});
