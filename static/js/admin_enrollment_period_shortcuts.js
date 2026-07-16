(function () {
  'use strict';

  var PERIODS = [
    { label: '1개월', months: 1 },
    { label: '2개월', months: 2 },
    { label: '3개월', months: 3 },
    { label: '6개월', months: 6 },
    { label: '1년', months: 12 }
  ];

  function parseDate(value) {
    var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec((value || '').trim());
    if (!match) {
      return null;
    }
    var year = Number(match[1]);
    var month = Number(match[2]) - 1;
    var day = Number(match[3]);
    var date = new Date(year, month, day);
    if (date.getFullYear() !== year || date.getMonth() !== month || date.getDate() !== day) {
      return null;
    }
    return date;
  }

  function formatDate(date) {
    var year = date.getFullYear();
    var month = String(date.getMonth() + 1).padStart(2, '0');
    var day = String(date.getDate()).padStart(2, '0');
    return year + '-' + month + '-' + day;
  }

  function addMonths(date, months) {
    var targetYear = date.getFullYear();
    var targetMonth = date.getMonth() + months;
    var targetDay = date.getDate();
    var lastDay = new Date(targetYear, targetMonth + 1, 0).getDate();
    return new Date(targetYear, targetMonth, Math.min(targetDay, lastDay));
  }

  function dispatchFieldChange(input) {
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function buildButtons(startInput, endInput) {
    var wrapper = document.createElement('span');
    wrapper.className = 'onedu-admin-period-shortcuts';
    wrapper.setAttribute('aria-label', '수강 종료일 빠른 설정');

    PERIODS.forEach(function (period) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'onedu-admin-period-shortcut';
      button.textContent = period.label;
      button.addEventListener('click', function () {
        var startDate = parseDate(startInput.value);
        if (!startDate) {
          startInput.focus();
          wrapper.classList.add('is-invalid');
          return;
        }
        wrapper.classList.remove('is-invalid');
        var endDate = addMonths(startDate, period.months);
        endDate.setDate(endDate.getDate() - 1);
        endInput.value = formatDate(endDate);
        dispatchFieldChange(endInput);
      });
      wrapper.appendChild(button);
    });

    var help = document.createElement('span');
    help.className = 'onedu-admin-period-shortcuts__help';
    help.textContent = '시작일을 먼저 입력해 주세요.';
    wrapper.appendChild(help);

    return wrapper;
  }

  function initEnrollmentPeriodShortcuts() {
    var startInput = document.getElementById('id_start_date');
    var endInput = document.getElementById('id_end_date');
    if (!startInput || !endInput || document.querySelector('.onedu-admin-period-shortcuts')) {
      return;
    }

    var shortcuts = buildButtons(startInput, endInput);
    var target = endInput.closest('p.date') || endInput.parentNode;
    target.appendChild(shortcuts);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEnrollmentPeriodShortcuts);
  } else {
    initEnrollmentPeriodShortcuts();
  }
}());
