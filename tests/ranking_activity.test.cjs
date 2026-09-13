const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('src/lolscout/web/static/app.js', 'utf8');
const loader = source.slice(source.indexOf('async function loadRankingActivity('), source.indexOf('function renderLive('));

test('bounded loading, session reuse, refresh and navigation cancellation', async () => {
  const cache = new Map();
  let active = 0, peak = 0, calls = 0, current = true;
  const rendered = [];
  const context = vm.createContext({
    URLSearchParams, Date, JSON, Promise,
    state: { platform: 'EUW1' },
    content: { querySelector: selector => selector },
    isCurrentContentRequest: () => current,
    sessionStorage: { getItem: key => cache.get(key) || null, setItem: (key, value) => cache.set(key, value) },
    renderRowActivity: (row, activity) => rendered.push([row, activity]),
    getJson: async () => {
      calls++; active++; peak = Math.max(peak, active);
      await new Promise(resolve => setImmediate(resolve));
      active--;
      return { recent_matches: [], lp_change: 0 };
    },
  });
  vm.runInContext(loader, context);
  const data = { players: Array.from({ length: 6 }, (_, i) => ({ ok: true, player: { game_name: `Player${i}`, tag_line: 'EUW' } })) };
  const request = { controller: new AbortController() };
  await context.loadRankingActivity(data, request);
  assert.equal(peak, 2);
  assert.equal(calls, 6);
  assert.equal(rendered.length, 6);
  await context.loadRankingActivity(data, request);
  assert.equal(calls, 6);
  await context.loadRankingActivity(data, request, true);
  assert.equal(calls, 12);
  rendered.length = 0;
  const pending = context.loadRankingActivity(data, request, true);
  current = false;
  await pending;
  assert.equal(rendered.length, 0);
  assert.equal(calls, 14);
});
