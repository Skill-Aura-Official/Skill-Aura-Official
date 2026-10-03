const DAY_MS = 86400000;

export function toUtcDay(value) {
  const date = new Date(value);
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
}

export function isoDay(value) {
  return toUtcDay(value).toISOString().slice(0, 10);
}

export function buildRollingWindow(now) {
  const end = toUtcDay(now);
  const start = new Date(end.getTime() - 364 * DAY_MS);
  return { start: isoDay(start), end: isoDay(end) };
}

export function sumDaily(daily, start, end) {
  return Object.entries(daily).filter(([day]) => day >= start && day <= end).reduce((sum, [, count]) => sum + count, 0);
}

export function calculateStreaks(daily, window) {
  const activeDays = new Set(Object.entries(daily).filter(([, count]) => count > 0).map(([day]) => day));
  const start = new Date(`${window.start}T00:00:00Z`);
  const end = new Date(`${window.end}T00:00:00Z`);
  let longest = 0;
  let longestStart = null;
  let longestEnd = null;
  let run = 0;
  let runStart = null;
  for (let cursor = new Date(start); cursor <= end; cursor = new Date(cursor.getTime() + DAY_MS)) {
    const day = isoDay(cursor);
    if (activeDays.has(day)) {
      if (run === 0) runStart = day;
      run += 1;
      if (run > longest) {
        longest = run;
        longestStart = runStart;
        longestEnd = day;
      }
    } else {
      run = 0;
      runStart = null;
    }
  }
  let current = 0;
  let currentStart = null;
  for (let cursor = new Date(end); cursor >= start; cursor = new Date(cursor.getTime() - DAY_MS)) {
    const day = isoDay(cursor);
    if (!activeDays.has(day)) break;
    current += 1;
    currentStart = day;
  }
  return {
    current,
    currentStart,
    currentEnd: current ? window.end : null,
    longest,
    longestStart,
    longestEnd
  };
}

export function stabilizeGeneratedAt(previous, current) {
  if (!previous?.generatedAt) return current;
  const { generatedAt: _previous, ...previousComparable } = previous;
  const { generatedAt: _current, ...currentComparable } = current;
  return JSON.stringify(previousComparable) === JSON.stringify(currentComparable)
    ? { ...current, generatedAt: previous.generatedAt }
    : current;
}

function escapeXml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[character]);
}

function compact(value) {
  return Number(value).toLocaleString('en-US');
}

function snapshot(isoString) {
  return `${isoString.slice(0, 10)} ${isoString.slice(11, 16)} UTC`;
}

function dateRange(start, end) {
  if (!start || !end) return 'No active streak';
  if (start === end) return start;
  return `${start} → ${end}`;
}

function icon(kind, x, y) {
  const common = `transform="translate(${x} ${y})" fill="none" stroke="#7dd3fc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"`;
  if (kind === 'star') return `<g ${common}><path d="M12 2.8l2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/></g>`;
  if (kind === 'commit') return `<g ${common}><circle cx="5" cy="12" r="3"/><circle cx="19" cy="12" r="3"/><path d="M8 12h8"/></g>`;
  if (kind === 'pull') return `<g ${common}><circle cx="6" cy="5" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="M6 8v9a2 2 0 002 2h7M18 16V8a3 3 0 00-3-3h-3"/></g>`;
  if (kind === 'issue') return `<g ${common}><circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 17h.01"/></g>`;
  return `<g ${common}><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M7 9h10M7 14h6"/></g>`;
}

export function renderGitHubStats(stats, mobile = false) {
  const metrics = stats.githubStats;
  const coverage = stats.scope.skillAuraProjects ? Math.round(metrics.contributedRepositoriesLastYear / stats.scope.skillAuraProjects * 100) : 0;
  const circumference = 2 * Math.PI * (mobile ? 70 : 78);
  const dash = circumference * coverage / 100;
  const rows = [
    ['star', 'TOTAL STARS EARNED', metrics.totalStars],
    ['commit', 'TRACKED COMMITS', metrics.totalCommits],
    ['pull', 'PULL REQUESTS', metrics.totalPullRequests],
    ['issue', 'ISSUES', metrics.totalIssues],
    ['repo', 'ACTIVE REPOSITORIES · 12M', metrics.contributedRepositoriesLastYear]
  ];
  if (mobile) {
    const rowMarkup = rows.map(([kind, label, value], index) => {
      const y = 198 + index * 70;
      return `${icon(kind, 54, y - 20)}<text x="94" y="${y - 5}" class="label">${label}</text><text x="650" y="${y + 5}" text-anchor="end" class="value">${compact(value)}</text><line x1="50" y1="${y + 29}" x2="670" y2="${y + 29}" stroke="#1f2c40"/>`;
    }).join('');
    return `<svg xmlns="http://www.w3.org/2000/svg" width="720" height="700" viewBox="0 0 720 700" role="img" aria-labelledby="statsTitle statsDesc"><title id="statsTitle">SkillAura GitHub Stats</title><desc id="statsDesc">Portfolio repository statistics from the twelve approved SkillAura projects: ${metrics.totalStars} stars, ${metrics.totalCommits} default-branch commits, ${metrics.totalPullRequests} pull requests, ${metrics.totalIssues} issues, and ${metrics.contributedRepositoriesLastYear} repositories active in the last twelve months.</desc><defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#070b14"/><stop offset=".55" stop-color="#10172a"/><stop offset="1" stop-color="#0a1020"/></linearGradient><linearGradient id="edge"><stop stop-color="#38bdf8"/><stop offset=".55" stop-color="#8b5cf6"/><stop offset="1" stop-color="#f59e0b"/></linearGradient></defs><style>.eyebrow{font:700 12px ui-monospace,monospace;fill:#879bb6;letter-spacing:1.4px}.title{font:800 31px ui-sans-serif,system-ui;fill:#f8fafc}.label{font:700 12px ui-monospace,monospace;fill:#a9b9cd;letter-spacing:.7px}.value{font:800 27px ui-sans-serif,system-ui;fill:#f8fafc}.score{font:800 43px ui-sans-serif,system-ui;fill:#f8fafc}.small{font:600 10px ui-monospace,monospace;fill:#71849e;letter-spacing:.5px}.status{font:800 10px ui-monospace,monospace;fill:#70e1c1;letter-spacing:1px}</style><rect x="4" y="4" width="712" height="692" rx="28" fill="#040711" stroke="#172033" stroke-width="8"/><rect x="10" y="10" width="700" height="680" rx="22" fill="url(#bg)" stroke="url(#edge)" stroke-opacity=".75"/><circle cx="44" cy="46" r="5" fill="#41d7b2"/><text x="58" y="50" class="status">SYNCED</text><text x="674" y="50" text-anchor="end" class="small">${escapeXml(snapshot(stats.generatedAt))}</text><text x="42" y="105" class="eyebrow">SKILLAURA // PORTFOLIO INTELLIGENCE</text><text x="42" y="145" class="title">GitHub Stats</text>${rowMarkup}<g transform="translate(360 606)"><circle r="70" fill="#0b1220" stroke="#24324a" stroke-width="13"/><circle r="70" fill="none" stroke="#8b5cf6" stroke-width="13" stroke-linecap="round" stroke-dasharray="${dash.toFixed(1)} ${circumference.toFixed(1)}" transform="rotate(-90)"/><text y="4" text-anchor="middle" class="score">${coverage}%</text><text y="28" text-anchor="middle" class="small">ACTIVE COVERAGE</text></g><text x="42" y="670" class="small">APPROVED SKILLAURA PROJECTS · FORK + EXTERNAL WORK EXCLUDED</text></svg>`;
  }
  const rowMarkup = rows.map(([kind, label, value], index) => {
    const column = index < 3 ? 0 : 1;
    const row = column === 0 ? index : index - 3;
    const x = column === 0 ? 62 : 425;
    const y = 174 + row * 82;
    return `${icon(kind, x, y - 23)}<text x="${x + 40}" y="${y - 7}" class="label">${label}</text><text x="${x + 40}" y="${y + 24}" class="value">${compact(value)}</text>`;
  }).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="460" viewBox="0 0 1200 460" role="img" aria-labelledby="statsTitle statsDesc"><title id="statsTitle">SkillAura GitHub Stats</title><desc id="statsDesc">Portfolio repository statistics from the twelve approved SkillAura projects: ${metrics.totalStars} stars, ${metrics.totalCommits} default-branch commits, ${metrics.totalPullRequests} pull requests, ${metrics.totalIssues} issues, and ${metrics.contributedRepositoriesLastYear} repositories active in the last twelve months.</desc><defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#070b14"/><stop offset=".55" stop-color="#10172a"/><stop offset="1" stop-color="#0a1020"/></linearGradient><linearGradient id="edge"><stop stop-color="#38bdf8"/><stop offset=".55" stop-color="#8b5cf6"/><stop offset="1" stop-color="#f59e0b"/></linearGradient><radialGradient id="glow"><stop stop-color="#7c3aed" stop-opacity=".2"/><stop offset="1" stop-color="#7c3aed" stop-opacity="0"/></radialGradient></defs><style>.eyebrow{font:700 12px ui-monospace,monospace;fill:#879bb6;letter-spacing:1.5px}.title{font:800 31px ui-sans-serif,system-ui;fill:#f8fafc}.label{font:700 11px ui-monospace,monospace;fill:#92a6c0;letter-spacing:.8px}.value{font:800 28px ui-sans-serif,system-ui;fill:#f8fafc}.score{font:800 47px ui-sans-serif,system-ui;fill:#f8fafc}.small{font:600 10px ui-monospace,monospace;fill:#71849e;letter-spacing:.55px}.status{font:800 10px ui-monospace,monospace;fill:#70e1c1;letter-spacing:1px}</style><rect x="4" y="4" width="1192" height="452" rx="28" fill="#040711" stroke="#172033" stroke-width="8"/><rect x="10" y="10" width="1180" height="440" rx="22" fill="url(#bg)" stroke="url(#edge)" stroke-opacity=".75"/><ellipse cx="1010" cy="210" rx="240" ry="220" fill="url(#glow)"/><circle cx="44" cy="44" r="5" fill="#41d7b2"/><text x="58" y="48" class="status">SYNCED</text><text x="1154" y="48" text-anchor="end" class="small">UPDATED AUTOMATICALLY · ${escapeXml(snapshot(stats.generatedAt))}</text><line x1="38" y1="67" x2="1162" y2="67" stroke="#26344a"/><text x="48" y="105" class="eyebrow">SKILLAURA // PORTFOLIO INTELLIGENCE</text><text x="48" y="145" class="title">GitHub Stats</text>${rowMarkup}<line x1="786" y1="110" x2="786" y2="398" stroke="#26344a"/><g transform="translate(991 242)"><circle r="78" fill="#0b1220" stroke="#24324a" stroke-width="14"/><circle r="78" fill="none" stroke="#8b5cf6" stroke-width="14" stroke-linecap="round" stroke-dasharray="${dash.toFixed(1)} ${circumference.toFixed(1)}" transform="rotate(-90)"/><text y="5" text-anchor="middle" class="score">${coverage}%</text><text y="31" text-anchor="middle" class="small">ACTIVE COVERAGE</text></g><text x="991" y="354" text-anchor="middle" class="label">${metrics.contributedRepositoriesLastYear} OF ${stats.scope.skillAuraProjects} PROJECTS</text><text x="991" y="377" text-anchor="middle" class="small">ACTIVE IN ROLLING 12 MONTHS</text><text x="48" y="425" class="small">APPROVED SKILLAURA PROJECTS · FORK + EXTERNAL WORK EXCLUDED</text></svg>`;
}

export function renderContributionActivity(stats, mobile = false) {
  const contribution = stats.contributionActivity;
  const items = [
    [compact(contribution.totalTrackedContributions), 'TRACKED CONTRIBUTIONS', `${stats.activity.window.start} → ${stats.activity.window.end}`],
    [compact(contribution.currentStreak), 'CURRENT STREAK', dateRange(contribution.currentStart, contribution.currentEnd)],
    [compact(contribution.longestStreak), 'LONGEST STREAK', dateRange(contribution.longestStart, contribution.longestEnd)]
  ];
  if (mobile) {
    const cards = items.map(([value, label, detail], index) => `<g transform="translate(42 ${125 + index * 128})"><rect width="636" height="106" rx="16" fill="#0f1829" stroke="#26344a"/><text x="24" y="49" class="number">${escapeXml(value)}</text><text x="612" y="41" text-anchor="end" class="label">${escapeXml(label)}</text><text x="612" y="66" text-anchor="end" class="detail">${escapeXml(detail)}</text></g>`).join('');
    return `<svg xmlns="http://www.w3.org/2000/svg" width="720" height="560" viewBox="0 0 720 560" role="img" aria-labelledby="activityTitle activityDesc"><title id="activityTitle">SkillAura Contribution Activity</title><desc id="activityDesc">Rolling twelve-month tracked repository contribution total, current active-day streak, and longest active-day streak for the approved SkillAura project scope.</desc><style>.title{font:800 28px ui-sans-serif,system-ui;fill:#f8fafc}.number{font:800 39px ui-sans-serif,system-ui;fill:#f8fafc}.label{font:800 12px ui-monospace,monospace;fill:#b6c5d8;letter-spacing:.8px}.detail{font:600 10px ui-monospace,monospace;fill:#71849e}.small{font:600 10px ui-monospace,monospace;fill:#71849e}</style><rect width="720" height="560" rx="24" fill="#080e1b"/><text x="42" y="62" class="title">Contribution Activity</text><text x="678" y="61" text-anchor="end" class="small">REPOSITORY ACTIVITY · UTC DAYS</text>${cards}<text x="42" y="532" class="small">DEFAULT-BRANCH COMMITS · ALL AUTHORS + AUTOMATION</text></svg>`;
  }
  const cards = items.map(([value, label, detail], index) => `<g transform="translate(${42 + index * 376} 105)"><rect width="354" height="135" rx="18" fill="#0f1829" stroke="#26344a"/><text x="177" y="61" text-anchor="middle" class="number">${escapeXml(value)}</text><text x="177" y="88" text-anchor="middle" class="label">${escapeXml(label)}</text><text x="177" y="113" text-anchor="middle" class="detail">${escapeXml(detail)}</text></g>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="290" viewBox="0 0 1200 290" role="img" aria-labelledby="activityTitle activityDesc"><title id="activityTitle">SkillAura Contribution Activity</title><desc id="activityDesc">Rolling twelve-month tracked repository contribution total, current active-day streak, and longest active-day streak for the approved SkillAura project scope.</desc><style>.title{font:800 27px ui-sans-serif,system-ui;fill:#f8fafc}.number{font:800 40px ui-sans-serif,system-ui;fill:#f8fafc}.label{font:800 11px ui-monospace,monospace;fill:#b6c5d8;letter-spacing:.8px}.detail{font:600 10px ui-monospace,monospace;fill:#71849e}.small{font:600 10px ui-monospace,monospace;fill:#71849e}</style><rect width="1200" height="290" rx="24" fill="#080e1b"/><text x="42" y="58" class="title">Contribution Activity</text><text x="1158" y="57" text-anchor="end" class="small">REPOSITORY ACTIVITY · UTC DAYS</text>${cards}<text x="42" y="270" class="small">DEFAULT-BRANCH COMMITS · ALL AUTHORS + AUTOMATION</text></svg>`;
}
