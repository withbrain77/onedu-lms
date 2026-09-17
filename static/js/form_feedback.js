(function () {
  'use strict';
  const pending = new Map();
  let leaving = false;
  function reset() {
    leaving = false;
    pending.forEach((state, form) => {
      form.removeAttribute('aria-busy');
      state.status.remove();
      state.buttons.forEach(button => button.removeAttribute('aria-disabled'));
    });
    pending.clear();
  }
  // Keep submitter names/values intact: Django uses them for admin actions.
  document.addEventListener('submit', function (event) {
    if (pending.has(event.target)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);
  window.addEventListener('submit', function (event) {
    const form = event.target;
    if (event.defaultPrevented || form.method.toLowerCase() !== 'post' || form.target === '_blank') return;
    leaving = true;
    const status = document.createElement('p');
    status.className = 'onedu-form-status';
    status.setAttribute('role', 'status');
    status.textContent = form.querySelector('input[type=file]')
      ? '저장 중입니다. 파일이 크면 시간이 걸릴 수 있습니다. 잠시 기다려 주세요.'
      : '처리 중입니다. 잠시 기다려 주세요.';
    const submitter = event.submitter;
    if (submitter) submitter.after(status);
    else form.append(status);
    const buttons = Array.from(form.querySelectorAll('button[type=submit], input[type=submit], button:not([type])'));
    buttons.forEach(button => button.setAttribute('aria-disabled', 'true'));
    form.setAttribute('aria-busy', 'true');
    pending.set(form, {status, buttons});
  });
  document.addEventListener('click', function (event) {
    const button = event.target.closest('button, input[type=submit]');
    if (button && pending.has(button.form)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);
  window.addEventListener('pageshow', reset);

  // Only editing forms warn on navigation; filters and login forms do not.
  const editForm = document.querySelector('body.change-form #content-main > form');
  if (editForm) {
    const snapshot = () => JSON.stringify([
      Array.from(new FormData(editForm)).filter(([name]) => name !== 'csrfmiddlewaretoken')
        .map(([name, value]) => [name,
          value instanceof File ? (value.name ? [value.name, value.size, value.lastModified] : null) : value]),
      // Django's permission chooser moves options without dispatching input.
      Array.from(editForm.querySelectorAll('select[id$="_to"]')).map(select =>
        [select.name, Array.from(select.options, option => option.value)]),
    ]);
    let initial = snapshot();
    window.addEventListener('load', () => { initial = snapshot(); }, {once: true});
    window.addEventListener('beforeunload', function (event) {
      if (!leaving && snapshot() !== initial) { event.preventDefault(); event.returnValue = ''; }
    });
  }
})();
