import assert from 'node:assert/strict';
import test from 'node:test';
import { buildRollingWindow, calculateStreaks, renderContributionActivity, renderGitHubStats, stabilizeGeneratedAt, sumDaily } from '../scripts/github-stats.mjs';

const generatedAt = '2026-10-03T08:00:00.000Z';
const window = buildRollingWindow(generatedAt);

function fixture(daily = { '2026-09-28': 7 }) {
  const streaks = calculateStreaks(daily, window);
  return {
    generatedAt,
    scope: { skillAuraProjects: 12 },
    activity: { window, last12Months: sumDaily(daily, window.start, window.end), daily },
    githubStats: { totalStars: 5, totalCommits: 500, totalPullRequests: 12, totalIssues: 9, contributedRepositoriesLastYear: 6 },
    contributionActivity: {
      totalTrackedContributions: sumDaily(daily, window.start, window.end),
      currentStreak: streaks.current,
      currentStart: streaks.currentStart,
      currentEnd: streaks.currentEnd,
      longestStreak: streaks.longest,
      longestStart: streaks.longestStart,
      longestEnd: streaks.longestEnd
    }
  };
}

test('rolling window covers 365 inclusive UTC days', () => {
  assert.equal(window.start, '2025-10-04');
  assert.equal(window.end, '2026-10-03');
});

test('same inputs produce identical stats and activity assets', () => {
  const data = fixture();
  assert.equal(renderGitHubStats(data), renderGitHubStats(data));
  assert.equal(renderContributionActivity(data), renderContributionActivity(data));
});

test('changed live metrics change the rendered stats dashboard', () => {
  const before = fixture();
  const after = { ...before, githubStats: { ...before.githubStats, totalStars: 6 } };
  assert.notEqual(renderGitHubStats(before), renderGitHubStats(after));
  assert.match(renderGitHubStats(after), /6 stars/);
});

test('streaks are derived from actual consecutive activity dates', () => {
  const streaks = calculateStreaks({ '2026-09-29': 1, '2026-09-30': 2, '2026-10-01': 1, '2026-10-03': 1 }, window);
  assert.equal(streaks.current, 1);
  assert.equal(streaks.longest, 3);
  assert.equal(streaks.longestStart, '2026-09-29');
  assert.equal(streaks.longestEnd, '2026-10-01');
});

test('unchanged source data preserves timestamp and avoids empty commits', () => {
  const previous = { generatedAt: '2026-10-03T02:00:00.000Z', value: 12 };
  const current = { generatedAt, value: 12 };
  assert.equal(stabilizeGeneratedAt(previous, current).generatedAt, previous.generatedAt);
  assert.equal(stabilizeGeneratedAt(previous, { ...current, value: 13 }).generatedAt, generatedAt);
});
