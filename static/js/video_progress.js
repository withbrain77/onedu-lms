(function () {
  const video = document.getElementById('lessonVideo');
  if (!video) {
    return;
  }

  const progressUrl = video.dataset.progressUrl;
  const hlsUrl = video.dataset.hlsUrl;
  const saveInterval = Number(video.dataset.saveInterval || 12000);
  const startPosition = Number(video.dataset.startPosition || 0);
  const playerShell = document.getElementById('videoPlayerShell');
  const watermark = document.getElementById('videoWatermark');
  const fullscreenButton = document.getElementById('videoFullscreenButton');
  const zoomLayer = document.getElementById('videoZoomLayer');
  const zoomMenu = document.getElementById('videoZoomMenu');
  const zoomToggle = document.getElementById('videoZoomToggle');
  const zoomControls = document.getElementById('videoZoomControls');
  const zoomResetButton = document.getElementById('videoZoomReset');
  const statusEl = document.getElementById('progressSaveStatus');
  const percentEl = document.getElementById('progressPercentText');
  const progressBar = document.getElementById('lessonProgressBar');
  const durationText = document.getElementById('lessonDurationText');
  const lastPositionText = document.getElementById('lessonLastPositionText');
  const totalWatchedText = document.getElementById('lessonTotalWatchedText');
  let hasRestoredPosition = false;
  const progressKey = video.dataset.progressKey;
  const sync = window.oneduProgressSync;
  let watchedSeconds = 0;
  let playbackRunning = false;
  let hasPlayed = false;
  let sampleAt = performance.now();
  let samplePosition = video.currentTime;
  let zoomScale = 1;
  let zoomX = 0;
  let zoomY = 0;
  let activePointerId = null;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragStartZoomX = 0;
  let dragStartZoomY = 0;
  let pinchActive = false;
  let pinchStartDistance = 0;
  let pinchStartScale = 1;
  let lastTapAt = 0;
  let lastTapX = 0;
  let lastTapY = 0;
  let touchStartX = 0;
  let touchStartY = 0;
  let touchMoved = false;
  let ignoreNextTap = false;
  let controlsHideTimer = null;
  const zoomLevels = [1, 1.25, 1.5, 2, 3];
  const controlsAutoHideDelay = 10000;
  const watermarkPositions = [
    'wm-pos-center',
    'wm-pos-top-left',
    'wm-pos-top-right',
    'wm-pos-mid-left',
    'wm-pos-mid-right',
    'wm-pos-bottom-left',
    'wm-pos-bottom-right',
  ];

  function setupHlsPlayback() {
    if (!hlsUrl) {
      return;
    }
    if (window.Hls && window.Hls.isSupported()) {
      const hls = new window.Hls({
        enableWorker: true,
        lowLatencyMode: false,
      });
      hls.loadSource(hlsUrl);
      hls.attachMedia(video);
      hls.on(window.Hls.Events.ERROR, function (_event, data) {
        if (data && data.fatal) {
          setStatus('영상 스트리밍 오류');
        }
      });
      return;
    }
    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = hlsUrl;
    }
  }

  function setStatus(message) {
    if (statusEl) {
      statusEl.textContent = message;
    }
  }

  function safeSeconds(value) {
    const seconds = Math.floor(Number(value || 0));
    if (!Number.isFinite(seconds) || seconds < 0) {
      return 0;
    }
    return seconds;
  }

  function formatSeconds(value) {
    const totalSeconds = safeSeconds(value);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    if (hours > 0) {
      return `${hours}시간 ${minutes}분 ${seconds}초`;
    }
    if (minutes > 0) {
      return `${minutes}분 ${seconds}초`;
    }
    return `${seconds}초`;
  }

  function setTimeText(element, seconds) {
    if (!element) {
      return;
    }
    const safeValue = safeSeconds(seconds);
    element.dataset.seconds = String(safeValue);
    element.textContent = formatSeconds(safeValue);
  }

  function updateTimeUI(data) {
    setTimeText(durationText, data.duration_seconds);
    setTimeText(lastPositionText, data.last_position_seconds);
    setTimeText(totalWatchedText, data.total_watched_seconds);
  }

  function updateProgressUI(percent) {
    const safePercent = Math.max(0, Math.min(Number(percent || 0), 100));
    if (percentEl) {
      percentEl.textContent = `${safePercent}%`;
    }
    if (progressBar) {
      progressBar.style.width = `${safePercent}%`;
    }
  }

  function randomWatermarkDelay() {
    return 10000 + Math.floor(Math.random() * 10000);
  }

  function moveWatermark() {
    if (!watermark) {
      return;
    }
    const currentPosition = watermarkPositions.find((position) => watermark.classList.contains(position));
    const candidates = watermarkPositions.filter((position) => position !== currentPosition);
    const nextPosition = candidates[Math.floor(Math.random() * candidates.length)];
    watermark.classList.remove(...watermarkPositions);
    watermark.classList.add(nextPosition);
  }

  function scheduleWatermarkMove() {
    if (!watermark) {
      return;
    }
    window.setTimeout(function () {
      moveWatermark();
      scheduleWatermarkMove();
    }, randomWatermarkDelay());
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function roundZoom(value) {
    return Math.round(value * 100) / 100;
  }

  function zoomPanLimit() {
    if (!playerShell || zoomScale <= 1) {
      return { x: 0, y: 0 };
    }
    const rect = playerShell.getBoundingClientRect();
    return {
      x: Math.max(0, (rect.width * (zoomScale - 1)) / 2),
      y: Math.max(0, (rect.height * (zoomScale - 1)) / 2),
    };
  }

  function clampZoomPan() {
    const limit = zoomPanLimit();
    zoomX = clamp(zoomX, -limit.x, limit.x);
    zoomY = clamp(zoomY, -limit.y, limit.y);
  }

  function updateZoomLabel() {
    if (zoomResetButton) {
      zoomResetButton.textContent = `${Math.round(zoomScale * 100)}%`;
    }
  }

  function setZoomMenuOpen(isOpen) {
    if (!zoomMenu || !zoomToggle || !zoomControls) {
      return;
    }
    zoomMenu.classList.toggle('is-open', isOpen);
    if (playerShell) {
      playerShell.classList.toggle('is-video-menu-open', isOpen);
    }
    zoomToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    zoomControls.hidden = !isOpen;
  }

  function shouldAutoHideControls() {
    return video && !video.paused && !video.ended;
  }

  function clearControlsHideTimer() {
    if (controlsHideTimer) {
      window.clearTimeout(controlsHideTimer);
      controlsHideTimer = null;
    }
  }

  function setControlsHidden(isHidden) {
    if (!playerShell) {
      return;
    }
    if (isHidden && zoomControls && !zoomControls.hidden) {
      setZoomMenuOpen(false);
    }
    playerShell.classList.toggle('are-video-controls-hidden', isHidden);
  }

  function scheduleControlsAutoHide() {
    clearControlsHideTimer();
    if (!shouldAutoHideControls()) {
      setControlsHidden(false);
      return;
    }
    controlsHideTimer = window.setTimeout(function () {
      if (shouldAutoHideControls()) {
        setControlsHidden(true);
      }
    }, controlsAutoHideDelay);
  }

  function revealCustomControls() {
    setControlsHidden(false);
    scheduleControlsAutoHide();
  }

  function applyZoom() {
    if (!zoomLayer) {
      return;
    }
    if (zoomScale <= 1.01) {
      zoomScale = 1;
      zoomX = 0;
      zoomY = 0;
    }
    clampZoomPan();
    zoomLayer.style.transform = `translate3d(${zoomX}px, ${zoomY}px, 0) scale(${zoomScale})`;
    if (playerShell) {
      playerShell.classList.toggle('is-video-zoomed', zoomScale > 1);
    }
    updateZoomLabel();
  }

  function setZoom(nextScale) {
    zoomScale = roundZoom(clamp(nextScale, zoomLevels[0], zoomLevels[zoomLevels.length - 1]));
    applyZoom();
  }

  function stepZoom(direction) {
    const tolerance = 0.01;
    if (direction > 0) {
      const nextLevel = zoomLevels.find((level) => level > zoomScale + tolerance);
      setZoom(nextLevel || zoomLevels[zoomLevels.length - 1]);
      return;
    }
    const previousLevel = zoomLevels
      .slice()
      .reverse()
      .find((level) => level < zoomScale - tolerance);
    setZoom(previousLevel || zoomLevels[0]);
  }

  function resetZoom() {
    setZoom(1);
  }

  function isZoomControlTarget(target) {
    if (!target || typeof target.closest !== 'function') {
      return false;
    }
    return Boolean(
      (
        target.closest('.video-zoom-controls') ||
        target.closest('.video-zoom-toggle') ||
        target.closest('.video-fullscreen-button')
      )
    );
  }

  function isNativeControlArea(clientY) {
    const rect = video.getBoundingClientRect();
    const controlHeight = Math.min(84, Math.max(46, rect.height * 0.22));
    return clientY >= rect.bottom - controlHeight;
  }

  function touchDistance(touches) {
    const dx = touches[0].clientX - touches[1].clientX;
    const dy = touches[0].clientY - touches[1].clientY;
    return Math.sqrt((dx * dx) + (dy * dy));
  }

  function toggleTapZoom() {
    setZoom(zoomScale > 1 ? 1 : 1.5);
  }

  function currentFullscreenElement() {
    return document.fullscreenElement || document.webkitFullscreenElement || null;
  }

  function requestPlayerFullscreen() {
    if (!playerShell) {
      return;
    }
    if (playerShell.requestFullscreen) {
      playerShell.requestFullscreen();
    } else if (playerShell.webkitRequestFullscreen) {
      playerShell.webkitRequestFullscreen();
    }
  }

  function exitFullscreen() {
    if (document.exitFullscreen) {
      document.exitFullscreen();
    } else if (document.webkitExitFullscreen) {
      document.webkitExitFullscreen();
    }
  }

  function updateFullscreenButton() {
    if (!fullscreenButton) {
      return;
    }
    fullscreenButton.textContent = currentFullscreenElement() ? '전체화면 종료' : '전체화면';
    revealCustomControls();
    window.setTimeout(applyZoom, 80);
  }

  function samplePlayback() {
    const now = performance.now();
    const elapsed = Math.max(0, (now - sampleAt) / 1000);
    const advanced = video.currentTime - samplePosition;
    const rate = video.playbackRate || 1;
    // Count only advancing playback, excluding pauses, buffering and seek jumps.
    if (playbackRunning && !video.seeking && advanced > 0 && advanced <= elapsed * rate + 1) {
      watchedSeconds += Math.min(elapsed, advanced / rate);
    }
    sampleAt = now;
    samplePosition = video.currentTime;
  }

  function eventId() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, function (c) {
      return (Number(c) ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> Number(c) / 4).toString(16);
    });
  }

  function saveProgress(options) {
    if (!progressUrl || !sync || !video.dataset.enrollmentId || !hasPlayed) return;
    samplePlayback();
    let remaining = Math.floor(watchedSeconds);
    watchedSeconds -= remaining;
    do {
      const increment = Math.min(remaining, 60);
      sync.enqueue({
        key: progressKey, url: progressUrl,
        payload: {
          event_id: eventId(), recorded_at: new Date().toISOString(),
          enrollment_id: video.dataset.enrollmentId,
          position_seconds: safeSeconds(video.currentTime),
          duration_seconds: safeSeconds(video.duration),
          watched_increment_seconds: increment,
          completed: Boolean(options && options.completed),
        },
      });
      remaining -= increment;
    } while (remaining > 0);
  }

  window.addEventListener('onedu:progress-save', function (event) {
    const result = event.detail;
    if (result.key !== progressKey) return;
    if (result.state === 'saved') {
      updateProgressUI(result.data.progress_percent);
      updateTimeUI(result.data);
      setStatus(sync.latest(progressKey) ? '남은 진도 저장 중...' : '진도가 저장되었습니다.');
    } else {
      const messages = {
        saving: '진도 저장 중...',
        retry: '연결되면 진도를 자동으로 다시 저장합니다.',
        'retry-memory': '진도 저장을 재시도합니다. 저장될 때까지 이 화면을 유지해 주세요.',
        access: '진도를 저장하려면 로그인 상태와 수강 기간을 확인해 주세요.',
      };
      setStatus(messages[result.state] || '진도 저장 대기 중');
    }
  });

  setupHlsPlayback();
  updateTimeUI({
    duration_seconds: durationText ? durationText.dataset.seconds : 0,
    last_position_seconds: lastPositionText ? lastPositionText.dataset.seconds : 0,
    total_watched_seconds: totalWatchedText ? totalWatchedText.dataset.seconds : 0,
  });

  video.addEventListener('loadedmetadata', function () {
    if (Number.isFinite(video.duration) && video.duration > 0) {
      setTimeText(durationText, video.duration);
    }
    const pending = sync && sync.resume(progressKey);
    const pendingIsNewer = pending && (!video.dataset.positionRecordedAt || Date.parse(pending.payload.recorded_at) > Date.parse(video.dataset.positionRecordedAt));
    const position = pendingIsNewer ? pending.payload.position_seconds : startPosition;
    if (!hasRestoredPosition && position > 0 && Number.isFinite(video.duration)) {
      const restorePosition = Math.min(position, Math.max(video.duration - 2, 0));
      if (restorePosition > 0) {
        video.currentTime = restorePosition;
      }
      hasRestoredPosition = true;
    }
  });

  video.addEventListener('play', function () {
    hasPlayed = true;
    setStatus('학습 중');
    revealCustomControls();
  });

  video.addEventListener('pause', function () {
    saveProgress();
    playbackRunning = false;
    clearControlsHideTimer();
    setControlsHidden(false);
  });

  video.addEventListener('ended', function () {
    clearControlsHideTimer();
    setControlsHidden(false);
    saveProgress({ completed: true });
    playbackRunning = false;
  });

  video.addEventListener('timeupdate', samplePlayback);
  video.addEventListener('playing', function () {
    sampleAt = performance.now();
    samplePosition = video.currentTime;
    playbackRunning = true;
  });
  ['waiting', 'seeking'].forEach(function (name) {
    video.addEventListener(name, function () { samplePlayback(); playbackRunning = false; });
  });
  video.addEventListener('seeked', function () {
    sampleAt = performance.now();
    samplePosition = video.currentTime;
    playbackRunning = !video.paused && !video.ended;
  });
  video.addEventListener('ratechange', function () {
    sampleAt = performance.now();
    samplePosition = video.currentTime;
  });

  window.setInterval(function () {
    if (!video.paused && !video.ended) {
      saveProgress();
    }
  }, saveInterval);

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') {
      saveProgress();
      if (sync) sync.flush(progressKey);
    }
  });
  window.addEventListener('pagehide', function () {
    saveProgress({ completed: video.ended });
    if (sync) sync.flush(progressKey);
  });

  if (fullscreenButton && playerShell) {
    fullscreenButton.addEventListener('click', function () {
      revealCustomControls();
      if (currentFullscreenElement()) {
        exitFullscreen();
      } else {
        requestPlayerFullscreen();
      }
    });
    document.addEventListener('fullscreenchange', updateFullscreenButton);
    document.addEventListener('webkitfullscreenchange', updateFullscreenButton);
  }

  if (zoomControls && zoomLayer) {
    zoomControls.addEventListener('click', function (event) {
      const button = event.target && typeof event.target.closest === 'function'
        ? event.target.closest('[data-zoom-action]')
        : null;
      if (!button) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      revealCustomControls();
      const action = button.dataset.zoomAction;
      if (action === 'in') {
        stepZoom(1);
      } else if (action === 'out') {
        stepZoom(-1);
      } else {
        resetZoom();
      }
    });
  }

  if (zoomToggle && zoomMenu && zoomControls) {
    zoomToggle.addEventListener('click', function (event) {
      event.preventDefault();
      event.stopPropagation();
      revealCustomControls();
      setZoomMenuOpen(zoomControls.hidden);
    });

    document.addEventListener('click', function (event) {
      if (!zoomControls.hidden && !zoomMenu.contains(event.target)) {
        setZoomMenuOpen(false);
        scheduleControlsAutoHide();
      }
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        setZoomMenuOpen(false);
        revealCustomControls();
      }
    });

    setZoomMenuOpen(false);
  }

  if (playerShell) {
    ['mousemove', 'pointerdown', 'touchstart'].forEach(function (eventName) {
      playerShell.addEventListener(eventName, revealCustomControls, { passive: true });
    });

    playerShell.addEventListener('focusin', revealCustomControls);

    document.addEventListener('keydown', function () {
      if (currentFullscreenElement() === playerShell || playerShell.contains(document.activeElement)) {
        revealCustomControls();
      }
    });

    revealCustomControls();
  }

  if (playerShell && zoomLayer) {
    video.addEventListener('dblclick', function (event) {
      if (isZoomControlTarget(event.target) || isNativeControlArea(event.clientY)) {
        return;
      }
      event.preventDefault();
      toggleTapZoom();
    });

    playerShell.addEventListener('pointerdown', function (event) {
      if (
        zoomScale <= 1 ||
        isZoomControlTarget(event.target) ||
        isNativeControlArea(event.clientY) ||
        (event.pointerType === 'mouse' && event.button !== 0)
      ) {
        return;
      }
      activePointerId = event.pointerId;
      dragStartX = event.clientX;
      dragStartY = event.clientY;
      dragStartZoomX = zoomX;
      dragStartZoomY = zoomY;
      zoomLayer.classList.add('is-dragging');
      if (playerShell.setPointerCapture) {
        try {
          playerShell.setPointerCapture(event.pointerId);
        } catch (error) {
          // Some mobile browsers skip pointer capture during native media gestures.
        }
      }
      event.preventDefault();
    });

    playerShell.addEventListener('pointermove', function (event) {
      if (activePointerId === null || event.pointerId !== activePointerId) {
        return;
      }
      zoomX = dragStartZoomX + (event.clientX - dragStartX);
      zoomY = dragStartZoomY + (event.clientY - dragStartY);
      applyZoom();
      event.preventDefault();
    });

    function stopZoomDrag(event) {
      if (activePointerId === null || (event && event.pointerId !== activePointerId)) {
        return;
      }
      if (playerShell.releasePointerCapture && event) {
        try {
          playerShell.releasePointerCapture(event.pointerId);
        } catch (error) {
          // Pointer capture may already be released by the browser.
        }
      }
      activePointerId = null;
      zoomLayer.classList.remove('is-dragging');
    }

    playerShell.addEventListener('pointerup', stopZoomDrag);
    playerShell.addEventListener('pointercancel', stopZoomDrag);
    playerShell.addEventListener('pointerleave', stopZoomDrag);

    playerShell.addEventListener('touchstart', function (event) {
      if (isZoomControlTarget(event.target)) {
        return;
      }
      if (event.touches.length === 2) {
        pinchActive = true;
        pinchStartDistance = touchDistance(event.touches);
        pinchStartScale = zoomScale;
        ignoreNextTap = true;
        zoomLayer.classList.add('is-dragging');
        return;
      }
      if (event.touches.length === 1) {
        touchStartX = event.touches[0].clientX;
        touchStartY = event.touches[0].clientY;
        touchMoved = false;
      }
    }, { passive: true });

    playerShell.addEventListener('touchmove', function (event) {
      if (pinchActive && event.touches.length === 2 && pinchStartDistance > 0) {
        event.preventDefault();
        const nextScale = pinchStartScale * (touchDistance(event.touches) / pinchStartDistance);
        setZoom(nextScale);
        return;
      }
      if (event.touches.length === 1) {
        const dx = event.touches[0].clientX - touchStartX;
        const dy = event.touches[0].clientY - touchStartY;
        touchMoved = touchMoved || Math.sqrt((dx * dx) + (dy * dy)) > 14;
      }
    }, { passive: false });

    playerShell.addEventListener('touchend', function (event) {
      if (pinchActive && event.touches.length < 2) {
        pinchActive = false;
        zoomLayer.classList.remove('is-dragging');
        window.setTimeout(function () {
          ignoreNextTap = false;
        }, 280);
        return;
      }
      if (ignoreNextTap || event.touches.length > 0 || event.changedTouches.length !== 1) {
        return;
      }
      const touch = event.changedTouches[0];
      if (touchMoved || isNativeControlArea(touch.clientY)) {
        return;
      }
      const now = Date.now();
      const dx = touch.clientX - lastTapX;
      const dy = touch.clientY - lastTapY;
      const isDoubleTap = now - lastTapAt < 320 && Math.sqrt((dx * dx) + (dy * dy)) < 44;
      if (isDoubleTap) {
        event.preventDefault();
        toggleTapZoom();
        lastTapAt = 0;
      } else {
        lastTapAt = now;
        lastTapX = touch.clientX;
        lastTapY = touch.clientY;
      }
    }, { passive: false });

    window.addEventListener('resize', applyZoom);
    window.addEventListener('orientationchange', function () {
      window.setTimeout(applyZoom, 140);
    });

    applyZoom();
  }

  moveWatermark();
  scheduleWatermarkMove();
})();
