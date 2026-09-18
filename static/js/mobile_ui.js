(function () {
  'use strict';
  const bottomNav = document.querySelector('.mobile-bottom-nav');
  if (bottomNav) {
    function updateNavHeight() {
      const height = Math.ceil(bottomNav.getBoundingClientRect().height);
      document.documentElement.style.setProperty('--mobile-nav-height', height + 'px');
    }
    updateNavHeight();
    if ('ResizeObserver' in window) {
      const observer = new ResizeObserver(updateNavHeight);
      observer.observe(bottomNav);
    }
    window.addEventListener('resize', updateNavHeight);
  }

  document.querySelectorAll('input[type="password"]').forEach(function (input) {
    const wrapper = document.createElement('div');
    wrapper.className = 'password-field';
    input.before(wrapper);
    wrapper.append(input);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'password-toggle';
    button.textContent = '보기';
    button.setAttribute('aria-label', '비밀번호 표시');
    button.setAttribute('aria-pressed', 'false');
    if (input.id) button.setAttribute('aria-controls', input.id);
    button.addEventListener('click', function () {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      button.textContent = show ? '숨기기' : '보기';
      button.setAttribute('aria-label', show ? '비밀번호 숨기기' : '비밀번호 표시');
      button.setAttribute('aria-pressed', String(show));
    });
    wrapper.append(button);
  });

  const tabs = Array.from(document.querySelectorAll('[data-lesson-tab]'));
  if (tabs.length) {
    function selectTab(active) {
      tabs.forEach(function (tab) {
        const selected = tab === active;
        tab.setAttribute('aria-selected', String(selected));
        tab.tabIndex = selected ? 0 : -1;
        document.getElementById(tab.getAttribute('aria-controls')).hidden = !selected;
      });
    }
    tabs[0].parentElement.hidden = false;
    document.querySelectorAll('[data-lesson-panel]').forEach(function (panel) {
      panel.setAttribute('role', 'tabpanel');
      panel.tabIndex = 0;
    });
    tabs.forEach(function (tab, index) {
      tab.addEventListener('click', function () { selectTab(tab); });
      tab.addEventListener('keydown', function (event) {
        let next;
        if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
        if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        if (next === undefined) return;
        event.preventDefault();
        selectTab(tabs[next]);
        tabs[next].focus();
      });
    });
    selectTab(tabs[0]);
  }

  document.querySelectorAll('[data-list-filter]').forEach(function (list) {
    const controls = list.querySelector('[data-filter-controls]');
    if (!controls) return;
    const query = list.querySelector('[data-filter-query]');
    const incomplete = list.querySelector('[data-filter-incomplete]');
    const items = Array.from(list.querySelectorAll('[data-filter-item]'));
    controls.hidden = false;
    function filter() {
      const value = query.value.trim().normalize('NFC').toLocaleLowerCase();
      let count = 0;
      items.forEach(function (item) {
        const matched = item.dataset.title.normalize('NFC').toLocaleLowerCase().includes(value)
          && (!incomplete || !incomplete.checked || item.dataset.completed !== 'true');
        item.hidden = !matched;
        if (matched) count += 1;
      });
      list.querySelector('[data-filter-count]').textContent = count + '개 차시 / 전체 ' + items.length + '개';
      list.querySelector('[data-filter-empty]').hidden = count !== 0 || items.length === 0;
    }
    query.addEventListener('input', filter);
    if (incomplete) incomplete.addEventListener('change', filter);
    window.addEventListener('onedu:progress-save', function (event) {
      const video = document.getElementById('lessonVideo');
      if (!video || event.detail.key !== video.dataset.progressKey || event.detail.state !== 'saved') return;
      items.filter(item => item.dataset.current === 'true').forEach(item => {
        item.dataset.completed = String(event.detail.data.is_completed);
      });
      filter();
    });
    filter();
  });

  function fullscreenChanged() {
    document.body.classList.toggle('is-player-fullscreen', Boolean(document.fullscreenElement || document.webkitFullscreenElement));
  }
  document.addEventListener('fullscreenchange', fullscreenChanged);
  document.addEventListener('webkitfullscreenchange', fullscreenChanged);
  const video = document.getElementById('lessonVideo');
  if (video) {
    video.addEventListener('webkitbeginfullscreen', function () { document.body.classList.add('is-player-fullscreen'); });
    video.addEventListener('webkitendfullscreen', fullscreenChanged);
  }
  function keyboardChanged() {
    const inputFocused = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    const smallerViewport = window.visualViewport && window.innerHeight - window.visualViewport.height > 150;
    document.body.classList.toggle('is-keyboard-open', Boolean(inputFocused && smallerViewport));
  }
  if (window.visualViewport) window.visualViewport.addEventListener('resize', keyboardChanged);
  document.addEventListener('focusin', keyboardChanged);
  document.addEventListener('focusout', function () { setTimeout(keyboardChanged, 0); });
})();
