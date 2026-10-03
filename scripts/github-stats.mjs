const DAY_MS = 86400000;

export function toUtcDay(value) {
  const date = new Date(value);
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
}

export function isoDay(value) { return toUtcDay(value).toISOString().slice(0, 10); }

export function buildRollingWindow(now) {
  const end = toUtcDay(now);
  return { start: isoDay(new Date(end.getTime() - 364 * DAY_MS)), end: isoDay(end) };
}

export function sumDaily(daily, start, end) {
  return Object.entries(daily).filter(([day]) => day >= start && day <= end).reduce((sum, [, count]) => sum + count, 0);
}

export function monthlyActivity(daily, window) {
  const months = [];
  const end = new Date(`${window.end}T00:00:00Z`);
  for (let offset = 11; offset >= 0; offset -= 1) {
    const date = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth() - offset, 1));
    const key = date.toISOString().slice(0, 7);
    months.push({ key, label: date.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' }), commits: 0, days: 0 });
  }
  const byKey = new Map(months.map((month) => [month.key, month]));
  for (const [day, count] of Object.entries(daily)) {
    if (day < window.start || day > window.end || count <= 0) continue;
    const month = byKey.get(day.slice(0, 7));
    if (month) { month.commits += count; month.days += 1; }
  }
  return months;
}

export function calculateStreaks(daily, window) {
  const active = [...new Set(Object.entries(daily).filter(([day, count]) => day >= window.start && day <= window.end && count > 0).map(([day]) => day))].sort();
  let longest = 0; let longestStart = null; let longestEnd = null;
  let run = 0; let runStart = null; let previous = null;
  for (const day of active) {
    const contiguous = previous && (new Date(`${day}T00:00:00Z`) - new Date(`${previous}T00:00:00Z`) === DAY_MS);
    if (!contiguous) { run = 0; runStart = day; }
    run += 1;
    if (run > longest) { longest = run; longestStart = runStart; longestEnd = day; }
    previous = day;
  }
  const latestActivityDate = active.at(-1) || null;
  let current = 0; let currentStart = null;
  if (latestActivityDate) {
    const activeSet = new Set(active);
    for (let cursor = new Date(`${latestActivityDate}T00:00:00Z`); cursor >= new Date(`${window.start}T00:00:00Z`); cursor = new Date(cursor.getTime() - DAY_MS)) {
      const day = isoDay(cursor);
      if (!activeSet.has(day)) break;
      current += 1; currentStart = day;
    }
  }
  return { current, currentStart, currentEnd: latestActivityDate, latestActivityDate, longest, longestStart, longestEnd };
}

export function stabilizeGeneratedAt(previous, current) {
  if (!previous?.generatedAt) return current;
  const { generatedAt: _a, ...a } = previous;
  const { generatedAt: _b, ...b } = current;
  return JSON.stringify(a) === JSON.stringify(b) ? { ...current, generatedAt: previous.generatedAt } : current;
}

const esc = (value) => String(value).replace(/[&<>"']/g, (c) => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;' })[c]);
const fmt = (value) => Number(value).toLocaleString('en-US');
const stamp = (iso) => `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
const range = (a, b) => !a ? 'No qualifying activity' : a === b ? a : `${a} → ${b}`;

function ring(coverage, mobile) {
  const r = mobile ? 69 : 77; const circumference = 2 * Math.PI * r; const dash = circumference * coverage / 100;
  return `<circle r="${r}" fill="#0a1324" stroke="#25334b" stroke-width="13"/><circle r="${r}" fill="none" stroke="#8b5cf6" stroke-width="13" stroke-linecap="round" stroke-dasharray="${dash.toFixed(1)} ${circumference.toFixed(1)}" transform="rotate(-90)"/>`;
}

export function renderGitHubStats(stats, mobile = false) {
  const m = stats.githubStats;
  const coverage = stats.scope.statsProjects ? Math.round(m.activeRepositories12Months / stats.scope.statsProjects * 100) : 0;
  const rows = [
    ['★','STARS ON TRACKED REPOSITORIES',m.stars],
    ['●','TRACKED COMMITS · ALL TIME',m.allTimeDefaultBranchCommits],
    ['↗','PULL REQUESTS',m.pullRequests],
    ['!','ISSUES',m.issues],
    ['▣','ACTIVE REPOSITORIES · 12M',m.activeRepositories12Months]
  ];
  const defs = `<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#050914"/><stop offset=".55" stop-color="#10172a"/><stop offset="1" stop-color="#071827"/></linearGradient><linearGradient id="edge"><stop stop-color="#38bdf8"/><stop offset=".55" stop-color="#8b5cf6"/><stop offset="1" stop-color="#f59e0b"/></linearGradient></defs>`;
  const style = `<style>.t{font:800 31px ui-sans-serif,system-ui;fill:#f8fafc}.k{font:700 11px ui-monospace,monospace;fill:#91a5c0;letter-spacing:.65px}.v{font:800 29px ui-sans-serif,system-ui;fill:#f8fafc}.s{font:600 10px ui-monospace,monospace;fill:#71849e;letter-spacing:.45px}.ok{font:800 10px ui-monospace,monospace;fill:#5ee3bd;letter-spacing:1px}.i{font:800 17px ui-sans-serif,system-ui;fill:#7dd3fc}.score{font:800 45px ui-sans-serif,system-ui;fill:#f8fafc}</style>`;
  if (mobile) {
    const list = rows.map(([icon,label,value],i)=>{const y=185+i*67;return `<text x="48" y="${y}" class="i">${icon}</text><text x="82" y="${y-2}" class="k">${label}</text><text x="670" y="${y+4}" text-anchor="end" class="v">${fmt(value)}</text><line x1="42" y1="${y+27}" x2="678" y2="${y+27}" stroke="#1f2c40"/>`;}).join('');
    return `<svg xmlns="http://www.w3.org/2000/svg" width="720" height="690" viewBox="0 0 720 690" role="img" aria-labelledby="title desc"><title id="title">Tracked Portfolio Activity</title><desc id="desc">Current repository activity for ${stats.scope.statsProjects} tracked SkillAura and approved Evisionindia repositories.</desc>${defs}${style}<rect x="6" y="6" width="708" height="678" rx="26" fill="url(#bg)" stroke="url(#edge)"/><circle cx="40" cy="40" r="5" fill="#41d7b2"/><text x="54" y="44" class="ok">SYNCED</text><text x="680" y="44" text-anchor="end" class="s">${esc(stamp(stats.generatedAt))}</text><text x="40" y="93" class="s">TRACKED PORTFOLIO // REPOSITORY ACTIVITY</text><text x="40" y="132" class="t">Portfolio Intelligence</text>${list}<g transform="translate(360 594)">${ring(coverage,true)}<text y="5" text-anchor="middle" class="score">${coverage}%</text><text y="29" text-anchor="middle" class="s">ACTIVE COVERAGE</text></g><text x="360" y="674" text-anchor="middle" class="s">${m.activeRepositories12Months} OF ${stats.scope.statsProjects} REPOSITORIES · FORK EXCLUDED</text></svg>`;
  }
  const list = rows.map(([icon,label,value],i)=>{const col=i<3?0:1;const row=col?i-3:i;const x=54+col*365;const y=177+row*79;return `<text x="${x}" y="${y}" class="i">${icon}</text><text x="${x+35}" y="${y-13}" class="k">${label}</text><text x="${x+35}" y="${y+20}" class="v">${fmt(value)}</text>`;}).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="450" viewBox="0 0 1200 450" role="img" aria-labelledby="title desc"><title id="title">Tracked Portfolio Activity</title><desc id="desc">Current repository activity for ${stats.scope.statsProjects} tracked SkillAura and approved Evisionindia repositories.</desc>${defs}${style}<rect x="6" y="6" width="1188" height="438" rx="26" fill="url(#bg)" stroke="url(#edge)"/><circle cx="40" cy="40" r="5" fill="#41d7b2"/><text x="54" y="44" class="ok">SYNCED</text><text x="1160" y="44" text-anchor="end" class="s">UPDATED AUTOMATICALLY · ${esc(stamp(stats.generatedAt))}</text><line x1="36" y1="66" x2="1164" y2="66" stroke="#26344a"/><text x="44" y="103" class="s">TRACKED PORTFOLIO // REPOSITORY ACTIVITY</text><text x="44" y="140" class="t">Portfolio Intelligence</text>${list}<line x1="785" y1="106" x2="785" y2="398" stroke="#26344a"/><g transform="translate(988 237)">${ring(coverage,false)}<text y="5" text-anchor="middle" class="score">${coverage}%</text><text y="29" text-anchor="middle" class="s">ACTIVE COVERAGE</text></g><text x="988" y="349" text-anchor="middle" class="k">${m.activeRepositories12Months} OF ${stats.scope.statsProjects} REPOSITORIES</text><text x="988" y="372" text-anchor="middle" class="s">ACTIVE IN ROLLING 12 MONTHS</text><text x="44" y="424" class="s">SKILLAURA + APPROVED EVISION PROFESSIONAL WORK · FORK EXCLUDED</text></svg>`;
}

function trend(total, skillAura, external, mobile) {
  const max = Math.max(1, ...total.map((m)=>m.commits));
  const width = mobile ? 46 : 73; const gap = mobile ? 6 : 14; const baseX = mobile ? 42 : 48; const baseY = mobile ? 650 : 354; const maxH = mobile ? 112 : 100;
  return total.map((m,i)=>{const s=skillAura[i]?.commits||0,e=external[i]?.commits||0;const sh=Math.round(s/max*maxH),eh=Math.round(e/max*maxH);const x=baseX+i*(width+gap);return `<g><rect x="${x}" y="${baseY-sh-eh}" width="${width}" height="${Math.max(e?3:0,eh)}" rx="4" fill="#38bdf8"><title>${esc(m.key)} external professional: ${e} commits</title></rect><rect x="${x}" y="${baseY-sh}" width="${width}" height="${Math.max(s?3:0,sh)}" rx="4" fill="#8b5cf6"><title>${esc(m.key)} SkillAura: ${s} commits</title></rect><text x="${x+width/2}" y="${baseY+18}" text-anchor="middle" class="month">${esc(m.label)}</text><text x="${x+width/2}" y="${baseY-sh-eh-6}" text-anchor="middle" class="count">${m.commits||''}</text></g>`;}).join('');
}

export function renderContributionActivity(stats, mobile = false) {
  const c = stats.contributionActivity;
  const items = [[fmt(c.rollingCommits),'ROLLING 12M COMMITS',`${stats.activity.window.start} → ${stats.activity.window.end}`],[fmt(c.contributionDays),'CONTRIBUTION DAYS','Days with ≥1 tracked commit'],[fmt(c.currentStreak),'CURRENT STREAK',range(c.currentStart,c.currentEnd)],[fmt(c.longestStreak),'LONGEST STREAK',range(c.longestStart,c.longestEnd)]];
  const style=`<style>.t{font:800 28px ui-sans-serif,system-ui;fill:#f8fafc}.n{font:800 38px ui-sans-serif,system-ui;fill:#f8fafc}.k{font:800 11px ui-monospace,monospace;fill:#b6c5d8;letter-spacing:.7px}.d{font:600 9.5px ui-monospace,monospace;fill:#71849e}.s{font:600 10px ui-monospace,monospace;fill:#71849e}.month{font:600 9px ui-monospace,monospace;fill:#71849e}.count{font:700 8px ui-monospace,monospace;fill:#cbd5e1}</style>`;
  const legend=`<circle cx="0" cy="0" r="5" fill="#8b5cf6"/><text x="12" y="4" class="s">SKILLAURA</text><circle cx="110" cy="0" r="5" fill="#38bdf8"/><text x="122" y="4" class="s">EXTERNAL / PROFESSIONAL</text>`;
  if(mobile){const cards=items.map(([v,k,d],i)=>`<g transform="translate(42 ${105+i*94})"><rect width="636" height="78" rx="14" fill="#0f1829" stroke="#26344a"/><text x="22" y="47" class="n">${esc(v)}</text><text x="612" y="31" text-anchor="end" class="k">${esc(k)}</text><text x="612" y="53" text-anchor="end" class="d">${esc(d)}</text></g>`).join('');return `<svg xmlns="http://www.w3.org/2000/svg" width="720" height="720" viewBox="0 0 720 720" role="img" aria-labelledby="title desc"><title id="title">Tracked Portfolio Activity</title><desc id="desc">Combined rolling activity for SkillAura and approved Evisionindia repositories, with category-separated monthly commits.</desc>${style}<rect width="720" height="720" rx="24" fill="#080e1b"/><text x="42" y="57" class="t">Tracked Portfolio Activity</text><text x="678" y="56" text-anchor="end" class="s">REPOSITORY ACTIVITY · UTC</text>${cards}<text x="42" y="500" class="k">MONTHLY TRACKED COMMITS</text><g transform="translate(42 526)">${legend}</g>${trend(c.monthly,c.monthlySkillAura,c.monthlyExternal,true)}<text x="42" y="705" class="s">ALL AUTHORS + AUTOMATION · FORK EXCLUDED · NOT A PERSONAL CONTRIBUTION COUNT</text></svg>`;}
  const cards=items.map(([v,k,d],i)=>`<g transform="translate(${42+i*282} 92)"><rect width="264" height="112" rx="16" fill="#0f1829" stroke="#26344a"/><text x="132" y="48" text-anchor="middle" class="n">${esc(v)}</text><text x="132" y="73" text-anchor="middle" class="k">${esc(k)}</text><text x="132" y="94" text-anchor="middle" class="d">${esc(d)}</text></g>`).join('');return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="420" viewBox="0 0 1200 420" role="img" aria-labelledby="title desc"><title id="title">Tracked Portfolio Activity</title><desc id="desc">Combined rolling activity for SkillAura and approved Evisionindia repositories, with category-separated monthly commits.</desc>${style}<rect width="1200" height="420" rx="24" fill="#080e1b"/><text x="42" y="55" class="t">Tracked Portfolio Activity</text><text x="1158" y="54" text-anchor="end" class="s">DEFAULT-BRANCH REPOSITORY ACTIVITY · UTC</text>${cards}<text x="48" y="242" class="k">MONTHLY TRACKED COMMITS</text><g transform="translate(774 240)">${legend}</g>${trend(c.monthly,c.monthlySkillAura,c.monthlyExternal,false)}<text x="48" y="405" class="s">ALL AUTHORS + AUTOMATION · FORK EXCLUDED · NOT A PERSONAL CONTRIBUTION COUNT</text></svg>`;
}
