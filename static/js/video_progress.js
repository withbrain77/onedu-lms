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
  const statusEl = document.getElementById('progressSaveStatus');
  const percentEl = document.getElementById('progressPercentText');
  const progressBar = document.getElementById('lessonProgressBar');
  const durationText = document.getElementById('lessonDurationText');
  const lastPositionText = document.getElementById('lessonLastPositionText');
  const totalWatchedText = document.getElementById('lessonTotalWatchedText');
  let lastSaveAt = 0;
  let hasRestoredPosition = false;
  let saving = false;
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

  function csrfToken() {
    const token = document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrftoken='));
    return token ? decodeURIComponent(token.split('=')[1]) : '';
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
  }

  async function saveProgress(options) {
    if (!progressUrl || saving) {
      return;
    }

    const completed = Boolean(options && options.completed);
    const watchedIncrement = Math.max(0, Math.round((Date.now() - lastSaveAt) / 1000));
    const payload = {
      position_seconds: safeSeconds(video.currentTime),
      duration_seconds: safeSeconds(video.duration),
      watched_increment_seconds: Math.min(watchedIncrement, 60),
      completed: completed,
    };

    saving = true;
    setStatus('진도 저장 중...');
    try {
      const response = await fetch(progressUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        setStatus('진도 저장 실패');
        return;
      }

      const data = await response.json();
      if (data.ok) {
        updateProgressUI(data.progress_percent);
        updateTimeUI(data);
        setStatus(data.is_completed ? '시청 완료 저장됨' : '최근 진도 저장됨');
        lastSaveAt = Date.now();
      }
    } catch (error) {
      setStatus('진도 저장 실패');
    } finally {
      saving = false;
    }
  }

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
    if (!hasRestoredPosition && startPosition > 0 && Number.isFinite(video.duration)) {
      const restorePosition = Math.min(startPosition, Math.max(video.duration - 2, 0));
      if (restorePosition > 0) {
        video.currentTime = restorePosition;
      }
      hasRestoredPosition = true;
    }
  });

  video.addEventListener('play', function () {
    lastSaveAt = Date.now();
    setStatus('학습 중');
  });

  video.addEventListener('ended', function () {
    saveProgress({ completed: true });
  });

  window.setInterval(function () {
    if (!video.paused && !video.ended) {
      saveProgress();
    }
  }, saveInterval);

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden' && !video.paused && !video.ended) {
      saveProgress();
    }
  });

  if (fullscreenButton && playerShell) {
    fullscreenButton.addEventListener('click', function () {
      if (currentFullscreenElement()) {
        exitFullscreen();
      } else {
        requestPlayerFullscreen();
      }
    });
    document.addEventListener('fullscreenchange', updateFullscreenButton);
    document.addEventListener('webkitfullscreenchange', updateFullscreenButton);
  }

  moveWatermark();
  scheduleWatermarkMove();
})();
