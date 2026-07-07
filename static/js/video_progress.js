(function () {
  const video = document.getElementById('lessonVideo');
  if (!video) {
    return;
  }

  const progressUrl = video.dataset.progressUrl;
  const saveInterval = Number(video.dataset.saveInterval || 12000);
  const startPosition = Number(video.dataset.startPosition || 0);
  const statusEl = document.getElementById('progressSaveStatus');
  const percentEl = document.getElementById('progressPercentText');
  const progressBar = document.getElementById('lessonProgressBar');
  let lastSaveAt = 0;
  let hasRestoredPosition = false;
  let saving = false;

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

  function updateProgressUI(percent) {
    const safePercent = Math.max(0, Math.min(Number(percent || 0), 100));
    if (percentEl) {
      percentEl.textContent = `${safePercent}%`;
    }
    if (progressBar) {
      progressBar.style.width = `${safePercent}%`;
    }
  }

  async function saveProgress(options) {
    if (!progressUrl || saving) {
      return;
    }

    const completed = Boolean(options && options.completed);
    const watchedIncrement = Math.max(0, Math.round((Date.now() - lastSaveAt) / 1000));
    const payload = {
      position_seconds: Math.floor(video.currentTime || 0),
      duration_seconds: Math.floor(video.duration || 0),
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
        setStatus(data.is_completed ? '시청 완료 저장됨' : '최근 진도 저장됨');
        lastSaveAt = Date.now();
      }
    } catch (error) {
      setStatus('진도 저장 실패');
    } finally {
      saving = false;
    }
  }

  video.addEventListener('loadedmetadata', function () {
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
})();
