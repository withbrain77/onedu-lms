(function () {
  'use strict';
  var deferredPrompt = null;
  var installed = false;
  var dismissalKey = 'withbrain-install-dismissed-until';
  var standalone = window.matchMedia('(display-mode: standalone)');
  var mobile = window.matchMedia('(max-width: 767px)');
  var ua = navigator.userAgent;
  var ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  var android = /Android/i.test(ua);
  var inApp = /KAKAOTALK|NAVER|Instagram|FBAN|FBAV|Line\//i.test(ua);

  function each(selector, callback) {
    document.querySelectorAll(selector).forEach(callback);
  }
  function isInstalled() {
    return installed || standalone.matches || navigator.standalone === true;
  }
  function dismissed() {
    try { return Number(localStorage.getItem(dismissalKey)) > Date.now(); }
    catch (error) { return false; }
  }
  function status(message) {
    each('[data-install-status]', function (node) { node.textContent = message; });
  }
  function render() {
    var done = isInstalled();
    each('[data-install-promotion]', function (node) { node.hidden = done; });
    each('[data-install-banner]', function (node) { node.hidden = done || !mobile.matches || dismissed(); });
    each('[data-install-native]', function (node) { node.hidden = done || !deferredPrompt || inApp; });
    each('[data-install-inapp]', function (node) { node.hidden = done || !inApp; });
    each('[data-install-ios]', function (node) { node.hidden = android && !ios; });
    each('[data-install-android]', function (node) { node.hidden = ios; });
    each('[data-install-instructions]', function (node) { node.hidden = done; });
    if (done) { status('홈 화면에서 실행 중이거나 설치가 완료되었습니다. 내 강의실에서 학습을 이어가세요.'); }
  }
  async function install() {
    if (!deferredPrompt) { return; }
    var prompt = deferredPrompt;
    deferredPrompt = null;
    render();
    try {
      await prompt.prompt();
      var choice = await prompt.userChoice;
      if (choice.outcome === 'accepted') {
        status('추가 요청을 완료했습니다. 휴대폰 홈 화면이나 앱 목록에서 위드브레인을 확인해 주세요.');
      } else {
        status('추가를 취소했습니다. 아래 방법으로 언제든 다시 추가할 수 있어요.');
      }
    } catch (error) {
      status('설치창을 열지 못했습니다. 아래 브라우저 메뉴 안내에 따라 추가해 주세요.');
    }
  }
  window.addEventListener('beforeinstallprompt', function (event) {
    if (inApp || isInstalled()) { return; }
    event.preventDefault();
    deferredPrompt = event;
    render();
  });
  window.addEventListener('appinstalled', function () {
    installed = true;
    deferredPrompt = null;
    render();
  });
  document.addEventListener('DOMContentLoaded', function () {
    render();
    each('[data-install-link]', function (link) {
      link.addEventListener('click', function (event) {
        if (deferredPrompt && !inApp && !isInstalled()) { event.preventDefault(); install(); }
      });
    });
    each('[data-install-button]', function (button) { button.addEventListener('click', install); });
    each('[data-install-dismiss]', function (button) {
      button.addEventListener('click', function () {
        try { localStorage.setItem(dismissalKey, String(Date.now() + 7 * 24 * 60 * 60 * 1000)); }
        catch (error) { /* A blocked storage area must not prevent closing the banner. */ }
        each('[data-install-banner]', function (node) { node.hidden = true; });
      });
    });
    each('[data-install-copy]', function (button) {
      button.hidden = false;
      button.addEventListener('click', async function () {
        var input = document.getElementById('classroomAddress');
        try {
          if (!navigator.clipboard || !window.isSecureContext) { throw new Error('Clipboard unavailable'); }
          await navigator.clipboard.writeText(input.value);
          status('주소를 복사했습니다. Safari 또는 Chrome 주소창에 붙여넣어 주세요.');
        } catch (error) {
          input.focus();
          input.select();
          input.setSelectionRange(0, input.value.length);
          status('주소를 길게 눌러 복사한 뒤 Safari 또는 Chrome 주소창에 붙여넣어 주세요.');
        }
      });
    });
    if (standalone.addEventListener) { standalone.addEventListener('change', render); }
    if (mobile.addEventListener) { mobile.addEventListener('change', render); }
  });
})();
