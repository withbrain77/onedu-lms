(function () {
  'use strict';
  const input = document.getElementById('id_username');
  const status = document.querySelector('[data-username-availability]');
  if (!input || !status) return;
  const descriptions = new Set((input.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
  descriptions.add(status.id);
  input.setAttribute('aria-describedby', Array.from(descriptions).join(' '));
  let timer, controller, revision = 0;
  let checkedValue = null;

  function show(message, state) {
    status.hidden = !message;
    status.textContent = message;
    status.className = 'form-text' + (state === 'valid' ? ' text-success' : state === 'invalid' ? ' text-danger' : '');
    status.dataset.state = state;
    input.classList.toggle('is-invalid', state === 'invalid');
    input.classList.toggle('is-valid', state === 'valid');
    if (state === 'invalid') input.setAttribute('aria-invalid', 'true');
    else input.removeAttribute('aria-invalid');
  }

  async function check() {
    clearTimeout(timer);
    const value = input.value;
    if (checkedValue === value) return;
    if (!value) { show('', 'idle'); return; }
    if (!/^(?=.*[A-Za-z])(?=.*[0-9])[A-Za-z0-9]{1,20}$/.test(value)) {
      show('영문과 숫자를 모두 포함해 최대 20자로 입력해 주세요.', 'invalid');
      return;
    }
    if (controller) controller.abort();
    controller = new AbortController();
    const current = ++revision;
    show('아이디 사용 가능 여부를 확인하고 있습니다.', 'checking');
    try {
      const url = new URL(status.dataset.usernameAvailability, window.location.origin);
      url.searchParams.set('username', value);
      const response = await fetch(url, {signal: controller.signal, cache: 'no-store', headers: {Accept: 'application/json'}});
      if (!response.ok) throw new Error('Availability check failed');
      const result = await response.json();
      if (current !== revision || input.value !== value) return;
      if (typeof result.available !== 'boolean' || typeof result.message !== 'string') throw new Error('Invalid response');
      checkedValue = value;
      show(result.message, result.available ? 'valid' : 'invalid');
    } catch (error) {
      if (current !== revision || error.name === 'AbortError') return;
      show('지금은 중복 여부를 확인할 수 없습니다. 회원가입 시 다시 확인합니다.', 'unavailable');
    }
  }

  input.addEventListener('input', function () {
    clearTimeout(timer);
    revision += 1;
    checkedValue = null;
    if (controller) controller.abort();
    const serverErrors = document.getElementById(input.id + '_errors');
    if (serverErrors) serverErrors.hidden = true;
    delete input.dataset.serverInvalid;
    show('', 'idle');
    if (!input.composing) timer = setTimeout(check, 400);
  });
  input.addEventListener('compositionstart', function () { input.composing = true; clearTimeout(timer); });
  input.addEventListener('compositionend', function () { input.composing = false; timer = setTimeout(check, 400); });
  input.addEventListener('blur', function () { if (!input.composing) check(); });
})();
