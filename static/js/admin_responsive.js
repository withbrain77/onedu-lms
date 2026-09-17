(function () {
  'use strict';
  const compact = window.matchMedia('(max-width: 1120px)');
  const navigation = document.querySelector('.onedu-admin-navigation');
  const filter = document.getElementById('changelist-filter');
  let filterPanel;
  if (filter) {
    filterPanel = document.createElement('details');
    filterPanel.className = 'onedu-admin-filter-panel';
    const summary = document.createElement('summary');
    summary.textContent = document.getElementById('changelist-filter-clear') ? '필터 (적용 중)' : '필터';
    const heading = filter.querySelector('h2');
    if (heading) heading.remove();
    filterPanel.append(summary);
    while (filter.firstChild) filterPanel.append(filter.firstChild);
    filter.append(filterPanel);
  }
  function updateLayout() {
    if (navigation) navigation.open = !compact.matches;
    if (filterPanel) filterPanel.open = !compact.matches;
  }
  updateLayout();
  compact.addEventListener('change', updateLayout);

  document.querySelectorAll('#changelist .results, .onedu-admin-table-wrap').forEach(function (tableRegion) {
    const hint = document.createElement('p');
    hint.className = 'onedu-admin-table-hint';
    hint.textContent = '표를 좌우로 밀어 나머지 항목을 확인하세요.';
    tableRegion.before(hint);
    function updateOverflow() {
      const overflowing = tableRegion.scrollWidth > tableRegion.clientWidth + 1;
      hint.hidden = !overflowing;
      if (overflowing) {
        tableRegion.tabIndex = 0;
        tableRegion.setAttribute('role', 'region');
        tableRegion.setAttribute('aria-label', '좌우로 스크롤할 수 있는 목록');
      } else {
        tableRegion.removeAttribute('tabindex');
        tableRegion.removeAttribute('role');
        tableRegion.removeAttribute('aria-label');
      }
    }
    updateOverflow();
    if ('ResizeObserver' in window) new ResizeObserver(updateOverflow).observe(tableRegion);
    window.addEventListener('resize', updateOverflow);
  });
})();
