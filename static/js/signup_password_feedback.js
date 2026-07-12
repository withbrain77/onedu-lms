(function () {
  const form = document.querySelector('[data-password-feedback-form]');
  if (!form) {
    return;
  }

  const usernameInput = form.querySelector('#id_username');
  const nameInput = form.querySelector('#id_name');
  const emailInput = form.querySelector('#id_email');
  const passwordInput = form.querySelector('#id_password1');
  const confirmInput = form.querySelector('#id_password2');
  const summary = form.querySelector('[data-password-summary]');
  const matchMessage = form.querySelector('[data-password-match-message]');

  if (!passwordInput || !confirmInput || !summary) {
    return;
  }

  const commonPasswords = new Set([
    '12345678',
    '123456789',
    '1234567890',
    'password',
    'password1',
    'qwerty123',
    '11111111',
    '00000000',
    'abc12345',
    'admin123',
    'iloveyou',
  ]);

  const ruleElements = Array.from(form.querySelectorAll('[data-password-rule]'));

  function normalize(value) {
    return (value || '').trim().toLowerCase();
  }

  function textTokens(value) {
    return normalize(value)
      .split(/[^0-9a-z가-힣]+/i)
      .map((token) => token.trim())
      .filter((token) => token.length >= 3);
  }

  function isTooSimilar(password) {
    const normalizedPassword = normalize(password);
    if (normalizedPassword.length < 4) {
      return false;
    }

    const tokens = [
      ...textTokens(usernameInput && usernameInput.value),
      ...textTokens(nameInput && nameInput.value),
      ...textTokens(emailInput && emailInput.value.split('@')[0]),
    ];

    return tokens.some((token) => normalizedPassword.includes(token));
  }

  function isCommonPassword(password) {
    const normalizedPassword = normalize(password);
    return commonPasswords.has(normalizedPassword);
  }

  function setRuleState(rule, state) {
    const item = form.querySelector(`[data-password-rule="${rule}"]`);
    if (!item) {
      return;
    }

    const status = item.querySelector('[data-password-rule-status]');
    item.dataset.state = state;

    if (status) {
      if (state === 'pass') {
        status.textContent = '충족';
      } else if (state === 'fail') {
        status.textContent = '미충족';
      } else {
        status.textContent = '대기';
      }
    }
  }

  function updateInputState(input, isTouched, isValid) {
    if (!isTouched) {
      input.classList.remove('is-valid', 'is-invalid');
      return;
    }

    input.classList.toggle('is-valid', isValid);
    input.classList.toggle('is-invalid', !isValid);
  }

  function evaluate() {
    const password = passwordInput.value;
    const confirmation = confirmInput.value;
    const hasPassword = password.length > 0;
    const hasConfirmation = confirmation.length > 0;

    const results = {
      length: password.length >= 8,
      common: hasPassword && !isCommonPassword(password),
      numeric: hasPassword && !/^\d+$/.test(password),
      similar: hasPassword && !isTooSimilar(password),
      match: hasPassword && hasConfirmation && password === confirmation,
    };

    Object.entries(results).forEach(([rule, passed]) => {
      setRuleState(rule, !hasPassword && rule !== 'match' ? 'pending' : passed ? 'pass' : 'fail');
    });

    if (!hasConfirmation) {
      setRuleState('match', 'pending');
      if (matchMessage) {
        matchMessage.textContent = '비밀번호 확인값을 입력해 주세요.';
        matchMessage.className = 'password-match-hint form-text';
      }
    } else if (results.match) {
      if (matchMessage) {
        matchMessage.textContent = '비밀번호가 일치합니다.';
        matchMessage.className = 'password-match-hint form-text text-success fw-semibold';
      }
    } else if (matchMessage) {
      matchMessage.textContent = '비밀번호가 일치하지 않습니다.';
      matchMessage.className = 'password-match-hint form-text text-danger fw-semibold';
    }

    const passwordRulesPass = results.length && results.common && results.numeric && results.similar;
    const allPass = passwordRulesPass && results.match;

    if (!hasPassword) {
      summary.textContent = '입력 전';
      summary.dataset.state = 'pending';
    } else if (allPass) {
      summary.textContent = '모든 조건 충족';
      summary.dataset.state = 'pass';
    } else {
      summary.textContent = '확인 필요';
      summary.dataset.state = 'fail';
    }

    updateInputState(passwordInput, hasPassword, passwordRulesPass);
    updateInputState(confirmInput, hasConfirmation, results.match);
  }

  [usernameInput, nameInput, emailInput, passwordInput, confirmInput].forEach((input) => {
    if (input) {
      input.addEventListener('input', evaluate);
      input.addEventListener('blur', evaluate);
    }
  });

  ruleElements.forEach((item) => {
    item.dataset.state = 'pending';
  });
  evaluate();
})();
