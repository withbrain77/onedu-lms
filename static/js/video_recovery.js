(function () {
  'use strict';
  const video = document.getElementById('lessonVideo');
  if (!video) return;
  const panel = document.getElementById('playbackNotice');
  const message = document.getElementById('playbackNoticeText');
  const retry = document.getElementById('videoRetryButton');
  const action = document.getElementById('playbackAccessLink');
  let hls = null;
  let attempts = 0;
  let retryTimer = null;
  let stableTimer = null;
  let checking = false;
  let accessBlocked = false;
  let wantsPlayback = false;
  let lastPosition = Number(video.dataset.startPosition || 0);
  let restorePosition = null;
  let readyToPlay = false;

  function notice(text, canRetry) {
    panel.hidden = false;
    message.textContent = text;
    retry.hidden = !canRetry;
    action.hidden = true;
  }
  function stopRetries() {
    clearTimeout(retryTimer);
    clearTimeout(stableTimer);
    retryTimer = null;
  }
  function showAccess(code) {
    accessBlocked = true;
    stopRetries();
    video.pause();
    const login = code === 'login_required';
    const ended = code === 'ended';
    notice(login ? '로그인이 만료되었습니다. 다시 로그인하면 이 차시로 돌아옵니다.' :
      ended ? '수강 기간이 종료되었습니다. 강의 화면에서 재수강 가능 여부를 확인해 주세요.' :
      '현재 이 영상을 이용할 수 없습니다. 수강 상태를 확인해 주세요.', false);
    action.hidden = false;
    action.textContent = login ? '다시 로그인' : ended ? '재수강 확인' : '수강 상태 확인';
    action.href = login ? video.dataset.loginUrl + '?next=' + encodeURIComponent(location.pathname + location.search) : video.dataset.courseUrl;
  }
  async function checkAccess() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    try {
      const response = await fetch(video.dataset.accessUrl, {credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
      const data = await response.json();
      if ([401, 403, 404].includes(response.status)) { showAccess(data.code); return false; }
      if (!response.ok || !data.ok) throw new Error('Access check failed');
      return true;
    } catch (_) {
      notice('연결 상태를 확인해 주세요. 연결되면 재생을 다시 시도합니다.', true);
      return false;
    } finally { clearTimeout(timeout); }
  }
  function attachStream() {
    if (hls) { hls.destroy(); hls = null; }
    if (video.dataset.hlsUrl) {
      if (window.Hls && Hls.isSupported()) {
        hls = new Hls({enableWorker: true, lowLatencyMode: false});
        hls.on(Hls.Events.ERROR, function (_event, data) {
          if (data && data.fatal) failure();
        });
        hls.loadSource(video.dataset.hlsUrl);
        hls.attachMedia(video);
      } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = video.dataset.hlsUrl;
        video.load();
      } else {
        notice(window.Hls ? '이 브라우저에서는 영상을 재생할 수 없습니다. Safari 또는 Chrome에서 열어 주세요.' :
          '영상 재생 기능을 불러오지 못했습니다. 연결 상태를 확인한 뒤 새로고침해 주세요.', false);
        action.hidden = false;
        action.textContent = '새로고침';
        action.href = location.pathname + location.search;
      }
    } else {
      video.load();
    }
  }
  async function recover(manual) {
    if (checking) return;
    stopRetries();
    if (manual) { attempts = 0; accessBlocked = false; wantsPlayback = true; }
    if (accessBlocked) return;
    readyToPlay = false;
    checking = true;
    retry.disabled = true;
    let retryCheck = false;
    try {
      if (!navigator.onLine) { notice('인터넷 연결이 끊겼습니다. 연결되면 재생을 다시 시도합니다.', true); return; }
      attempts += 1;
      if (!await checkAccess()) { retryCheck = !accessBlocked; return; }
      restorePosition = lastPosition;
      video.dispatchEvent(new Event('onedu:playback-recovering'));
      notice('영상을 다시 연결하고 있습니다…', true);
      attachStream();
    } finally {
      checking = false;
      retry.disabled = false;
      if (retryCheck) failure();
    }
  }
  function failure() {
    clearTimeout(stableTimer);
    if (accessBlocked || retryTimer || checking) return;
    if (!navigator.onLine) { notice('인터넷 연결이 끊겼습니다. 연결되면 재생을 다시 시도합니다.', true); return; }
    if (attempts >= 3) {
      notice('영상을 불러오지 못했습니다. 연결 상태를 확인한 뒤 다시 재생해 주세요.', true);
      return;
    }
    notice('재생이 중단되어 다시 연결하고 있습니다…', true);
    retryTimer = setTimeout(() => recover(false), 1000 * Math.pow(2, attempts));
  }
  retry.addEventListener('click', function () {
    if (readyToPlay && !accessBlocked) {
      readyToPlay = false;
      video.play().catch(() => notice('영상 안의 재생 버튼을 눌러 주세요.', false));
    } else recover(true);
  });
  video.addEventListener('error', failure);
  video.addEventListener('play', function () { wantsPlayback = true; });
  video.addEventListener('pause', function () {
    if (!video.error && restorePosition === null && !checking) wantsPlayback = false;
  });
  video.addEventListener('timeupdate', function () {
    if (restorePosition === null && Number.isFinite(video.currentTime)) lastPosition = video.currentTime;
  });
  video.addEventListener('loadedmetadata', function () {
    if (restorePosition === null) return;
    if (Number.isFinite(video.duration)) video.currentTime = Math.min(restorePosition, Math.max(video.duration - 1, 0));
    restorePosition = null;
    if (wantsPlayback) video.play().catch(function () {
      readyToPlay = true;
      notice('연결되었습니다. 다시 재생 버튼을 눌러 주세요.', true);
    });
    else panel.hidden = true;
  });
  video.addEventListener('playing', function () {
    if (accessBlocked) { video.pause(); return; }
    panel.hidden = true;
    stopRetries();
    stableTimer = setTimeout(function () { if (!video.paused && !video.error) attempts = 0; }, 10000);
  });
  window.addEventListener('online', function () { if (!panel.hidden && !accessBlocked && attempts < 3) recover(false); });
  function saveAccessFailure(data) {
    if (data && data.code === 'invalid_event') {
      notice('진도를 저장하지 못했습니다. 새로고침 후 다시 시도해 주세요.', false);
    } else if (data && data.code) showAccess(data.code);
    else checkAccess();
  }
  window.addEventListener('onedu:progress-save', function (event) {
    if (event.detail.key !== video.dataset.progressKey || event.detail.state !== 'access') return;
    // A CSRF failure can also be a 403. Confirm the session before choosing the action.
    saveAccessFailure(event.detail.data);
  });
  window.addEventListener('pagehide', stopRetries);
  if (video.dataset.hlsUrl) attachStream();
  else if (video.error) failure();
  const accessFailure = window.oneduProgressSync && window.oneduProgressSync.accessFailure(video.dataset.progressKey);
  if (accessFailure) saveAccessFailure(accessFailure.data);
})();
