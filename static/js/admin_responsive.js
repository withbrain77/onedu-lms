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

  const resultTable = document.getElementById('result_list');
  if (resultTable && resultTable.tBodies[0]?.rows.length && !document.body.classList.contains('popup')) {
    const headers = Array.from(resultTable.tHead.rows[0].cells);
    // Reuse the original cells so editing, selection and permissions stay intact.
    Array.from(resultTable.tBodies[0].rows).forEach(function (row) {
      let hasAdditional = false;
      Array.from(row.cells).forEach(function (cell, index) {
        const label = document.createElement('span');
        label.className = 'onedu-card-field-label';
        label.textContent = headers[index]?.querySelector('.text')?.textContent.trim() || '선택';
        cell.prepend(label);
        if (index > 5 && !cell.querySelector('input:not([type=hidden]),select,textarea') && !cell.classList.contains('field-end_date')) {
          cell.classList.add('onedu-card-additional');
          hasAdditional = true;
        }
      });
      if (hasAdditional) {
        const cell = row.insertCell();
        cell.className = 'onedu-card-details-cell';
        const details = document.createElement('button');
        details.type = 'button';
        details.textContent = '추가 정보 펼치기';
        details.setAttribute('aria-expanded', 'false');
        details.addEventListener('click', () => {
          const expanded = row.classList.toggle('onedu-card-expanded');
          details.setAttribute('aria-expanded', String(expanded));
          details.textContent = expanded ? '추가 정보 접기' : '추가 정보 펼치기';
        });
        cell.append(details);
      }
    });
    const toolbar = document.createElement('div');
    toolbar.className = 'onedu-list-view-controls';
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.setAttribute('aria-controls', 'result_list');
    let cards = true;
    function updateCards() {
      resultTable.classList.toggle('onedu-card-list', cards && compact.matches);
      toggle.textContent = cards ? '표 보기' : '카드 보기';
      toggle.setAttribute('aria-label', cards ? '표 보기로 전환 (열 정렬 가능)' : '카드 보기로 전환');
      // Also update horizontal-scroll hints after switching views.
      window.dispatchEvent(new Event('resize'));
    }
    toggle.addEventListener('click', () => { cards = !cards; updateCards(); });
    toolbar.append(toggle);
    const selectAll = document.getElementById('action-toggle');
    if (selectAll) {
      const selectButton = document.createElement('button');
      selectButton.type = 'button';
      const updateSelection = () => {
        selectButton.textContent = selectAll.checked ? '전체 선택 해제' : '전체 선택';
        selectButton.setAttribute('aria-pressed', String(selectAll.checked));
      };
      selectButton.addEventListener('click', () => { selectAll.click(); updateSelection(); });
      resultTable.addEventListener('change', () => queueMicrotask(updateSelection));
      updateSelection();
      toolbar.append(selectButton);
    }
    resultTable.closest('.results').before(toolbar);
    compact.addEventListener('change', updateCards);
    updateCards();
  }

  document.querySelectorAll('#changelist .results, .onedu-admin-table-wrap, .inline-group .tabular').forEach(function (tableRegion) {
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
