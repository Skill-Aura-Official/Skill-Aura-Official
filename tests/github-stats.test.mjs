import assert from 'node:assert/strict';
import test from 'node:test';
import { buildRollingWindow, calculateStreaks, monthlyActivity, renderContributionActivity, renderGitHubStats, stabilizeGeneratedAt, sumDaily } from '../scripts/github-stats.mjs';

const generatedAt='2026-10-03T08:00:00.000Z';
const window=buildRollingWindow(generatedAt);
function fixture(daily={'2026-09-28':7}){const streaks=calculateStreaks(daily,window);const skillAura={'2026-09-28':4},external={'2026-09-28':3};return{generatedAt,scope:{statsProjects:15},activity:{window,daily},githubStats:{stars:5,allTimeDefaultBranchCommits:500,currentYearCommits:100,last90DaysCommits:50,last30DaysCommits:20,pullRequests:12,issues:9,activeRepositories12Months:6},contributionActivity:{rollingCommits:sumDaily(daily,window.start,window.end),contributionDays:Object.keys(daily).length,currentStreak:streaks.current,currentStart:streaks.currentStart,currentEnd:streaks.currentEnd,longestStreak:streaks.longest,longestStart:streaks.longestStart,longestEnd:streaks.longestEnd,monthly:monthlyActivity(daily,window),monthlySkillAura:monthlyActivity(skillAura,window),monthlyExternal:monthlyActivity(external,window)}};}

test('rolling window covers 365 inclusive UTC days',()=>{assert.deepEqual(window,{start:'2025-10-04',end:'2026-10-03'});});
test('current streak ends at latest qualifying date',()=>{const s=calculateStreaks({'2026-09-29':1,'2026-09-30':2,'2026-10-01':1,'2026-10-03':1},window);assert.equal(s.current,1);assert.equal(s.currentEnd,'2026-10-03');assert.equal(s.longest,3);});
test('stale latest activity still has a factual streak',()=>{const s=calculateStreaks({'2026-07-05':2,'2026-07-06':1},window);assert.equal(s.current,2);assert.equal(s.currentStart,'2026-07-05');assert.equal(s.currentEnd,'2026-07-06');});
test('monthly trend uses real commit counts and contribution days',()=>{const m=monthlyActivity({'2026-09-01':2,'2026-09-02':3},window).find((x)=>x.key==='2026-09');assert.deepEqual({commits:m.commits,days:m.days},{commits:5,days:2});});
test('renderers are deterministic and respond to metric changes',()=>{const a=fixture(),b={...a,githubStats:{...a.githubStats,stars:6}};assert.equal(renderContributionActivity(a),renderContributionActivity(a));assert.notEqual(renderGitHubStats(a),renderGitHubStats(b));assert.match(renderGitHubStats(b),/>6<\/text>/);});
test('activity renderer separates SkillAura and external professional categories',()=>{const svg=renderContributionActivity(fixture());assert.match(svg,/SKILLAURA/);assert.match(svg,/EXTERNAL \/ PROFESSIONAL/);assert.match(svg,/NOT A PERSONAL CONTRIBUTION COUNT/);});
test('unchanged data preserves timestamp',()=>{const previous={generatedAt:'2026-10-03T02:00:00.000Z',value:12};assert.equal(stabilizeGeneratedAt(previous,{generatedAt,value:12}).generatedAt,previous.generatedAt);assert.equal(stabilizeGeneratedAt(previous,{generatedAt,value:13}).generatedAt,generatedAt);});
