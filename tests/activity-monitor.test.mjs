import assert from 'node:assert/strict';
import test from 'node:test';
import { buildRollingWindow, renderActivityMonitor, renderActivityMonitorMobile, stabilizeGeneratedAt, sumDaily } from '../scripts/activity-monitor.mjs';

const generatedAt = '2026-10-03T08:00:00.000Z';
const window = buildRollingWindow(generatedAt);

function fixture(daily) {
  return {
    generatedAt,
    activity: {
      window,
      last12Months: sumDaily(daily, window.start, window.end),
      last90Days: 0,
      last30Days: 0,
      daily
    }
  };
}

test('rolling activity window covers 365 inclusive UTC days', () => {
  assert.equal(window.start, '2025-10-04');
  assert.equal(window.end, '2026-10-03');
  assert.ok(window.weeks === 53 || window.weeks === 54);
});

test('same repository data produces identical monitor output', () => {
  const data = fixture({ '2026-09-28': 7 });
  assert.equal(renderActivityMonitor(data), renderActivityMonitor(data));
  assert.equal(renderActivityMonitorMobile(data), renderActivityMonitorMobile(data));
});

test('changed input updates the total and corresponding daily cell', () => {
  const before = fixture({ '2026-09-28': 7 });
  const after = fixture({ '2026-09-28': 8 });
  const beforeSvg = renderActivityMonitor(before);
  const afterSvg = renderActivityMonitor(after);
  assert.notEqual(beforeSvg, afterSvg);
  assert.match(beforeSvg, /2026-09-28 — 7 repository commits/);
  assert.match(afterSvg, /2026-09-28 — 8 repository commits/);
  assert.match(afterSvg, />8<\/text>/);
  assert.match(renderActivityMonitorMobile(after), /2026-09-28 — 8 repository commits/);
});

test('unchanged data preserves snapshot time to avoid empty refresh commits', () => {
  const previous = { generatedAt: '2026-10-03T02:00:00.000Z', value: 12 };
  const current = { generatedAt: '2026-10-03T08:00:00.000Z', value: 12 };
  assert.equal(stabilizeGeneratedAt(previous, current).generatedAt, previous.generatedAt);
  assert.equal(stabilizeGeneratedAt(previous, { ...current, value: 13 }).generatedAt, current.generatedAt);
});
