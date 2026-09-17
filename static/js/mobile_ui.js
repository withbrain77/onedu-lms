(function () {
  'use strict';
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
