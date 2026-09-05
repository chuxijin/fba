(function () {
  'use strict';

  var script = document.currentScript;
  if (!script || !script.dataset.site || window.__webAnalyticsLoaded) return;
  window.__webAnalyticsLoaded = true;

  var site = script.dataset.site;
  var endpoint = (script.dataset.endpoint || new URL(script.src).origin + '/api/v1/analytics').replace(/\/$/, '');
  var queue = [];
  var flushTimer;
  var lastPath = '';
  var maxScroll = 0;
  var replayStop;

  function randomId() {
    return crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2);
  }

  function storageId(key, session) {
    try {
      var storage = session ? window.sessionStorage : window.localStorage;
      var value = storage.getItem(key);
      if (!value) {
        value = randomId();
        storage.setItem(key, value);
      }
      return value;
    } catch (_) {
      return randomId();
    }
  }

  var visitor = storageId('wa:visitor:' + site, false);
  var session = storageId('wa:session:' + site, true);
  var replay = storageId('wa:replay:' + site, true);

  function pagePath() {
    return location.pathname + location.search;
  }

  function send(url, payload) {
    var body = JSON.stringify(payload);
    if (navigator.sendBeacon && navigator.sendBeacon(url, new Blob([body], { type: 'text/plain' }))) return;
    fetch(url, { method: 'POST', body: body, headers: { 'Content-Type': 'text/plain' }, keepalive: true, credentials: 'omit', mode: 'no-cors' }).catch(function () {});
  }

  function event(type, name, properties) {
    queue.push({
      id: randomId(), type: type, name: name || null, path: pagePath(), title: document.title,
      referrer: document.referrer || null, timestamp: new Date().toISOString(), properties: properties || null,
      screen_width: screen.width, screen_height: screen.height,
      viewport_width: innerWidth, viewport_height: innerHeight
    });
    if (queue.length >= 10) flush();
    else if (!flushTimer) flushTimer = setTimeout(flush, 3000);
  }

  function flush() {
    clearTimeout(flushTimer);
    flushTimer = null;
    if (!queue.length) return;
    var events = queue.splice(0, 50);
    send(endpoint + '/collect', { site: site, visitor: visitor, session: session, events: events });
  }

  function pageview() {
    var path = pagePath();
    if (path === lastPath) return;
    lastPath = path;
    maxScroll = 0;
    event('pageview');
  }

  function wrapHistory(name) {
    var original = history[name];
    history[name] = function () {
      var result = original.apply(this, arguments);
      setTimeout(pageview, 0);
      return result;
    };
  }

  wrapHistory('pushState');
  wrapHistory('replaceState');
  addEventListener('popstate', pageview);
  addEventListener('hashchange', pageview);
  addEventListener('pagehide', flush);
  document.addEventListener('visibilitychange', function () { if (document.hidden) flush(); });

  document.addEventListener('click', function (e) {
    var target = e.target && e.target.closest ? e.target.closest('a,button,[role="button"],[data-analytics-click]') : null;
    if (!target || target.closest('[data-analytics-ignore]')) return;
    var rect = target.getBoundingClientRect();
    event('click', null, {
      x_ratio: Math.max(0, Math.min(1, e.clientX / Math.max(1, innerWidth))),
      y_ratio: Math.max(0, Math.min(1, (e.clientY + scrollY) / Math.max(1, document.documentElement.scrollHeight))),
      element: target.tagName.toLowerCase(),
      target: (target.id ? '#' + target.id : target.getAttribute('data-analytics-click') || '').slice(0, 128),
      element_x: Math.round(e.clientX - rect.left), element_y: Math.round(e.clientY - rect.top)
    });
  }, { passive: true });

  addEventListener('scroll', function () {
    var depth = Math.round((scrollY + innerHeight) / Math.max(1, document.documentElement.scrollHeight) * 100);
    [25, 50, 75, 90, 100].forEach(function (mark) {
      if (depth >= mark && maxScroll < mark) event('scroll', null, { depth: mark });
    });
    maxScroll = Math.max(maxScroll, depth);
  }, { passive: true });

  setInterval(function () { if (!document.hidden) event('heartbeat', null, { seconds: 15 }); }, 15000);

  try {
    new PerformanceObserver(function (list) {
      list.getEntries().forEach(function (entry) {
        var name = entry.entryType === 'largest-contentful-paint' ? 'LCP' : entry.name;
        if (name === 'LCP' || name === 'first-contentful-paint') event('web_vital', name, { value: Math.round(entry.startTime) });
      });
    }).observe({ type: 'largest-contentful-paint', buffered: true });
  } catch (_) {}

  function startReplay(options) {
    if (!window.rrweb || !window.rrweb.record || replayStop) return false;
    var chunks = [], sequence = 0;
    replayStop = window.rrweb.record({
      maskAllInputs: true, blockClass: 'analytics-block', maskTextClass: 'analytics-mask',
      emit: function (rrEvent) {
        chunks.push(rrEvent);
        if (chunks.length >= 100) {
          send(endpoint + '/replay', { site: site, visitor: visitor, session: session, replay: replay,
            sequence: sequence++, path: pagePath(), timestamp: new Date().toISOString(), events: chunks.splice(0) });
        }
      }
    });
    setInterval(function () {
      if (chunks.length) send(endpoint + '/replay', { site: site, visitor: visitor, session: session, replay: replay,
        sequence: sequence++, path: pagePath(), timestamp: new Date().toISOString(), events: chunks.splice(0) });
    }, (options && options.interval) || 30000);
    return true;
  }

  window.analytics = {
    track: function (name, properties) { event('custom', String(name).slice(0, 128), properties); },
    page: pageview,
    flush: flush,
    startReplay: startReplay
  };
  pageview();
})();
