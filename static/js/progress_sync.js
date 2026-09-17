/* Durable, per-user outbox. Each event has its own key so tabs cannot overwrite each other. */
(function () {
  'use strict';
  const pending = new Map();
  const resumeSnapshots = new Map();
  const blocked = new Map();
  let prefix = '';
  let busy = false;
  let storageAvailable = true;

  function remember(item) {
    const previous = resumeSnapshots.get(item.key);
    if (!previous || item.payload.recorded_at >= previous.payload.recorded_at) resumeSnapshots.set(item.key, item);
  }

  function report(item, state, data) {
    window.dispatchEvent(new CustomEvent('onedu:progress-save', { detail: { key: item.key, state, data } }));
  }
  function persist(item) {
    try { localStorage.setItem(prefix + item.payload.event_id, JSON.stringify(item)); }
    catch (_) { storageAvailable = false; }
  }
  function restore() {
    if (!prefix) return;
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (!key.startsWith(prefix)) continue;
        try {
          const item = JSON.parse(localStorage.getItem(key));
          // Only replay the same-origin progress endpoint; never send a CSRF token elsewhere.
          if (item && /^\/progress\/lessons\/\d+\/save\/$/.test(item.url) && item.payload && item.payload.event_id) {
            pending.set(item.payload.event_id, item);
            remember(item);
          }
        } catch (_) { /* Ignore damaged local entries. */ }
      }
    } catch (_) { storageAvailable = false; }
  }
  async function send(item) {
    const token = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
    if (!token) return false;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    report(item, 'saving');
    try {
      const response = await fetch(item.url, {
        method: 'POST', credentials: 'same-origin', keepalive: true, signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(token.slice(10)) },
        body: JSON.stringify(item.payload),
      });
      if (response.redirected || [400, 401, 403, 404, 409].includes(response.status)) {
        let data = response.redirected ? {code: 'login_required'} : null;
        if (!data) { try { data = await response.json(); } catch (_) { /* CSRF errors may be HTML. */ } }
        blocked.set(item.key, data);
        report(item, 'access', data);
        return false;
      }
      if (!response.ok) throw new Error('Save failed');
      const data = await response.json();
      if (!data.ok) throw new Error('Save rejected');
      pending.delete(item.payload.event_id);
      try { localStorage.removeItem(prefix + item.payload.event_id); } catch (_) { /* Retry remains idempotent. */ }
      report(item, 'saved', data);
      return true;
    } catch (_) {
      report(item, storageAvailable ? 'retry' : 'retry-memory');
      return false;
    } finally { clearTimeout(timeout); }
  }
  async function pump() {
    if (busy || !prefix || !navigator.onLine) return;
    busy = true;
    try {
      for (const item of pending.values()) {
        if (blocked.has(item.key)) continue;
        if (!await send(item) && !blocked.has(item.key)) break;
      }
    } finally { busy = false; }
  }
  window.oneduProgressSync = {
    enqueue(item) {
      if (!prefix) return;
      pending.set(item.payload.event_id, item);
      remember(item);
      persist(item);
      if (blocked.has(item.key)) { report(item, 'access', blocked.get(item.key)); return; }
      if (!navigator.onLine) report(item, storageAvailable ? 'retry' : 'retry-memory');
      pump();
    },
    latest(key) {
      return Array.from(pending.values()).filter(item => item.key === key)
        .sort((a, b) => b.payload.recorded_at.localeCompare(a.payload.recorded_at))[0];
    },
    resume(key) { return resumeSnapshots.get(key); },
    accessFailure(key) { return blocked.has(key) ? {data: blocked.get(key)} : null; },
    flush(key) {
      const item = this.latest(key);
      // Send the final position even when an earlier heartbeat is still in flight.
      if (item && !blocked.has(item.key)) send(item);
    },
  };
  function start() {
    const userId = document.body.dataset.userId;
    if (!userId) return;
    prefix = 'onedu-progress-v1:' + userId + ':';
    restore();
    pump();
    setInterval(pump, 15000);
  }
  start();
  window.addEventListener('online', function () { restore(); pump(); });
  window.addEventListener('storage', function (event) {
    if (!prefix || !event.key || !event.key.startsWith(prefix)) return;
    if (!event.newValue) pending.delete(event.key.slice(prefix.length));
    else { restore(); pump(); }
  });
})();
