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
  const gridStart = new Date(start);
  gridStart.setUTCDate(gridStart.getUTCDate() - gridStart.getUTCDay());
  const gridEnd = new Date(end);
  gridEnd.setUTCDate(gridEnd.getUTCDate() + (6 - gridEnd.getUTCDay()));
  const weeks = Math.round((gridEnd - gridStart) / (7 * DAY_MS)) + 1;
  return {
    start: isoDay(start),
    end: isoDay(end),
    gridStart: isoDay(gridStart),
    gridEnd: isoDay(gridEnd),
    weeks
  };
}

export function sumDaily(daily, start, end) {
  return Object.entries(daily)
    .filter(([day]) => day >= start && day <= end)
    .reduce((sum, [, count]) => sum + count, 0);
}

export function stabilizeGeneratedAt(previous, current) {
  if (!previous?.generatedAt) return current;
  const { generatedAt: _previousGeneratedAt, ...previousComparable } = previous;
  const { generatedAt: _currentGeneratedAt, ...currentComparable } = current;
  return JSON.stringify(previousComparable) === JSON.stringify(currentComparable)
    ? { ...current, generatedAt: previous.generatedAt }
    : current;
}

function escapeXml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;'
  })[character]);
}

function formatSnapshot(isoString) {
  const date = new Date(isoString);
  const day = date.toISOString().slice(0, 10);
  const time = date.toISOString().slice(11, 16);
  return `${day} ${time} UTC`;
}

export function renderActivityMonitor(stats) {
  const activity = stats.activity;
  const window = activity.window;
  const start = new Date(`${window.gridStart}T00:00:00Z`);
  const width = 1200;
  const height = 430;
  const gridX = 118;
  const gridY = 174;
  const gridWidth = 1030;
  const step = gridWidth / window.weeks;
  const cell = Math.min(13.5, step - 4.2);
  const cellOffset = (step - cell) / 2;
  const rowStep = 24;
  const values = Object.entries(activity.daily)
    .filter(([day]) => day >= window.start && day <= window.end)
    .map(([, count]) => count)
    .filter(Boolean)
    .sort((a, b) => a - b);
  const max = Math.max(1, ...values);
  const quartile = (ratio) => values.length ? values[Math.min(values.length - 1, Math.floor((values.length - 1) * ratio))] : 1;
  const thresholds = [quartile(0.25), quartile(0.5), quartile(0.75), max];
  const palette = ['#111a2b', '#143b65', '#176e9a', '#6042ba', '#9b5de5'];
  const colorFor = (count) => {
    if (!count) return palette[0];
    if (count <= thresholds[0]) return palette[1];
    if (count <= thresholds[1]) return palette[2];
    if (count <= thresholds[2]) return palette[3];
    return palette[4];
  };

  const cells = [];
  const months = [];
  let previousMonth = -1;
  let previousYear = -1;
  for (let week = 0; week < window.weeks; week += 1) {
    const weekDate = new Date(start);
    weekDate.setUTCDate(start.getUTCDate() + week * 7);
    const monthProbe = new Date(weekDate);
    monthProbe.setUTCDate(monthProbe.getUTCDate() + 3);
    if (monthProbe.getUTCMonth() !== previousMonth || monthProbe.getUTCFullYear() !== previousYear) {
      previousMonth = monthProbe.getUTCMonth();
      previousYear = monthProbe.getUTCFullYear();
      const label = monthProbe.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' }).toUpperCase();
      months.push(`<text x="${(gridX + week * step).toFixed(1)}" y="153" class="month">${label}</text>`);
    }
    for (let weekday = 0; weekday < 7; weekday += 1) {
      const date = new Date(weekDate);
      date.setUTCDate(weekDate.getUTCDate() + weekday);
      const day = isoDay(date);
      const active = day >= window.start && day <= window.end;
      const count = active ? (activity.daily[day] || 0) : 0;
      const fill = active ? colorFor(count) : '#0a101c';
      const stroke = count >= thresholds[2] && count > 0 ? '#b59bff' : (active ? '#26344a' : '#111827');
      const opacity = active ? 1 : 0.38;
      const x = gridX + week * step + cellOffset;
      const y = gridY + weekday * rowStep;
      cells.push(`<g opacity="${opacity}"><rect x="${x.toFixed(1)}" y="${y}" width="${cell.toFixed(1)}" height="${cell.toFixed(1)}" rx="3.5" fill="${fill}" stroke="${stroke}" stroke-width="0.8"><title>${day} — ${count} repository commit${count === 1 ? '' : 's'}</title></rect>${count >= thresholds[2] && count > 0 ? `<rect x="${(x + 2).toFixed(1)}" y="${y + 2}" width="${Math.max(1, cell - 4).toFixed(1)}" height="2" rx="1" fill="#ffffff" opacity=".24" pointer-events="none"/>` : ''}</g>`);
    }
  }

  const total = activity.last12Months.toLocaleString('en-US');
  const snapshot = formatSnapshot(stats.generatedAt);
  const dayLabels = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
    .map((label, index) => `<text x="90" y="${gridY + index * rowStep + 10}" text-anchor="end" class="day">${label}</text>`)
    .join('');
  const legend = palette.map((color, index) => `<rect x="${778 + index * 24}" y="374" width="15" height="15" rx="4" fill="${color}" stroke="#334155" stroke-width=".8"/>`).join('');

  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="430" viewBox="0 0 1200 430" role="img" aria-labelledby="activityTitle activityDescription">
  <title id="activityTitle">SkillAura engineering activity monitor</title>
  <desc id="activityDescription">A rolling twelve-month daily display of ${activity.last12Months} default-branch repository commits across twelve approved SkillAura projects, covering ${window.start} through ${window.end}.</desc>
  <defs>
    <linearGradient id="screenBackground" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#070b14"/><stop offset=".52" stop-color="#0d1524"/><stop offset="1" stop-color="#0a1020"/></linearGradient>
    <linearGradient id="screenEdge" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#38bdf8" stop-opacity=".72"/><stop offset=".54" stop-color="#8b5cf6" stop-opacity=".68"/><stop offset="1" stop-color="#f59e0b" stop-opacity=".48"/></linearGradient>
    <radialGradient id="screenGlow"><stop stop-color="#6d4aff" stop-opacity=".16"/><stop offset="1" stop-color="#6d4aff" stop-opacity="0"/></radialGradient>
    <filter id="cellGlow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <style>
    .eyebrow{font:700 12px ui-monospace,SFMono-Regular,Consolas,monospace;fill:#8da2bf;letter-spacing:1.8px}.title{font:800 18px ui-sans-serif,system-ui;fill:#edf4ff;letter-spacing:.6px}.metric{font:800 54px ui-sans-serif,system-ui;fill:#f8fafc}.metricLabel{font:700 12px ui-sans-serif,system-ui;fill:#9fb2cc;letter-spacing:1.7px}.month{font:700 10px ui-monospace,SFMono-Regular,Consolas,monospace;fill:#8194ad}.day{font:700 9px ui-monospace,SFMono-Regular,Consolas,monospace;fill:#657791}.small{font:600 10px ui-monospace,SFMono-Regular,Consolas,monospace;fill:#71849e;letter-spacing:.6px}.status{font:800 10px ui-monospace,SFMono-Regular,Consolas,monospace;fill:#70e1c1;letter-spacing:1.2px}
  </style>
  <rect x="4" y="4" width="1192" height="422" rx="28" fill="#040711" stroke="#172033" stroke-width="8"/>
  <rect x="10" y="10" width="1180" height="410" rx="22" fill="url(#screenBackground)" stroke="url(#screenEdge)" stroke-width="1.4"/>
  <rect x="21" y="21" width="1158" height="388" rx="17" fill="none" stroke="#26344a" stroke-width="1"/>
  <ellipse cx="925" cy="50" rx="260" ry="155" fill="url(#screenGlow)"/>
  <circle cx="43" cy="44" r="5" fill="#41d7b2" filter="url(#cellGlow)"/><text x="57" y="48" class="status">SYNCED</text>
  <text x="152" y="48" class="eyebrow">SKILLAURA // ENGINEERING ACTIVITY MONITOR</text>
  <text x="1152" y="48" text-anchor="end" class="small">ROLLING 12-MONTH WINDOW</text>
  <line x1="38" y1="65" x2="1162" y2="65" stroke="#26344a"/>
  <text x="41" y="116" class="metric">${escapeXml(total)}</text>
  <text x="${41 + Math.max(3, total.length) * 34}" y="96" class="metricLabel">REPOSITORY COMMITS</text>
  <text x="${41 + Math.max(3, total.length) * 34}" y="116" class="small">ACROSS APPROVED SKILLAURA PROJECTS · ALL AUTHORS + AUTOMATION</text>
  <text x="1152" y="95" text-anchor="end" class="small">${escapeXml(window.start)} → ${escapeXml(window.end)}</text>
  <text x="1152" y="116" text-anchor="end" class="small">12 PROJECTS · DEFAULT BRANCH HISTORY</text>
  ${months.join('')}
  ${dayLabels}
  ${cells.join('')}
  <line x1="38" y1="352" x2="1162" y2="352" stroke="#26344a"/>
  <text x="41" y="384" class="small">DAILY INTENSITY</text>
  <text x="738" y="386" text-anchor="end" class="small">LESS</text>${legend}<text x="916" y="386" class="small">MORE</text>
  <text x="1152" y="384" text-anchor="end" class="small">DATA SNAPSHOT ${escapeXml(snapshot)}</text>
  <text x="41" y="403" class="small">SOURCE: GITHUB REPOSITORY DATA · REFRESH SCHEDULE: EVERY 6 HOURS</text>
  </svg>`;
}

export function renderActivityMonitorMobile(stats) {
  const activity = stats.activity;
  const window = activity.window;
  const start = new Date(`${window.gridStart}T00:00:00Z`);
  const split = Math.ceil(window.weeks / 2);
  const bands = [[0, split], [split, window.weeks]];
  const values = Object.entries(activity.daily)
    .filter(([day]) => day >= window.start && day <= window.end)
    .map(([, count]) => count)
    .filter(Boolean)
    .sort((a, b) => a - b);
  const max = Math.max(1, ...values);
  const quartile = (ratio) => values.length ? values[Math.min(values.length - 1, Math.floor((values.length - 1) * ratio))] : 1;
  const thresholds = [quartile(0.25), quartile(0.5), quartile(0.75), max];
  const palette = ['#111a2b', '#143b65', '#176e9a', '#6042ba', '#9b5de5'];
  const colorFor = (count) => {
    if (!count) return palette[0];
    if (count <= thresholds[0]) return palette[1];
    if (count <= thresholds[1]) return palette[2];
    if (count <= thresholds[2]) return palette[3];
    return palette[4];
  };
  const gridX = 92;
  const gridWidth = 586;
  const rowStep = 26;
  const bandMarkup = bands.map(([firstWeek, lastWeek], bandIndex) => {
    const bandWeeks = lastWeek - firstWeek;
    const step = gridWidth / bandWeeks;
    const cell = Math.min(16, step - 5);
    const cellOffset = (step - cell) / 2;
    const gridY = bandIndex === 0 ? 238 : 500;
    const cells = [];
    const months = [];
    let previousMonth = -1;
    let previousYear = -1;
    for (let week = firstWeek; week < lastWeek; week += 1) {
      const weekDate = new Date(start);
      weekDate.setUTCDate(start.getUTCDate() + week * 7);
      const monthProbe = new Date(weekDate);
      monthProbe.setUTCDate(monthProbe.getUTCDate() + 3);
      if (monthProbe.getUTCMonth() !== previousMonth || monthProbe.getUTCFullYear() !== previousYear) {
        previousMonth = monthProbe.getUTCMonth();
        previousYear = monthProbe.getUTCFullYear();
        const label = monthProbe.toLocaleString('en-US', { month: 'short', timeZone: 'UTC' }).toUpperCase();
        months.push(`<text x="${(gridX + (week - firstWeek) * step).toFixed(1)}" y="${gridY - 20}" class="month">${label}</text>`);
      }
      for (let weekday = 0; weekday < 7; weekday += 1) {
        const date = new Date(weekDate);
        date.setUTCDate(weekDate.getUTCDate() + weekday);
        const day = isoDay(date);
        const active = day >= window.start && day <= window.end;
        const count = active ? (activity.daily[day] || 0) : 0;
        const fill = active ? colorFor(count) : '#0a101c';
        const stroke = count >= thresholds[2] && count > 0 ? '#b59bff' : (active ? '#26344a' : '#111827');
        const x = gridX + (week - firstWeek) * step + cellOffset;
        const y = gridY + weekday * rowStep;
        cells.push(`<rect x="${x.toFixed(1)}" y="${y}" width="${cell.toFixed(1)}" height="${cell.toFixed(1)}" rx="4" fill="${fill}" stroke="${stroke}" stroke-width="1" opacity="${active ? 1 : .38}"><title>${day} — ${count} repository commit${count === 1 ? '' : 's'}</title></rect>`);
      }
    }
    const firstDay = isoDay(new Date(start.getTime() + firstWeek * 7 * DAY_MS));
    const finalDate = new Date(start.getTime() + (lastWeek * 7 - 1) * DAY_MS);
    const finalDay = isoDay(finalDate > new Date(`${window.end}T00:00:00Z`) ? window.end : finalDate);
    const dayLabels = ['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((label, index) => `<text x="68" y="${gridY + index * rowStep + 12}" text-anchor="end" class="day">${label}</text>`).join('');
    return `<text x="42" y="${gridY - 48}" class="band">${escapeXml(firstDay)} → ${escapeXml(finalDay)}</text>${months.join('')}${dayLabels}${cells.join('')}`;
  }).join('');
  const snapshot = formatSnapshot(stats.generatedAt);
  const total = activity.last12Months.toLocaleString('en-US');
  const legend = palette.map((color, index) => `<rect x="${420 + index * 27}" y="750" width="17" height="17" rx="4" fill="${color}" stroke="#334155"/>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="720" height="820" viewBox="0 0 720 820" role="img" aria-labelledby="mobileTitle mobileDescription">
  <title id="mobileTitle">SkillAura engineering activity monitor for narrow screens</title>
  <desc id="mobileDescription">A mobile-readable rolling twelve-month display of ${activity.last12Months} default-branch repository commits across twelve approved SkillAura projects.</desc>
  <defs><linearGradient id="mobileBg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#070b14"/><stop offset=".55" stop-color="#0e1627"/><stop offset="1" stop-color="#0a1020"/></linearGradient><linearGradient id="mobileEdge" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#38bdf8" stop-opacity=".75"/><stop offset=".55" stop-color="#8b5cf6" stop-opacity=".7"/><stop offset="1" stop-color="#f59e0b" stop-opacity=".48"/></linearGradient></defs>
  <style>.eyebrow{font:700 13px ui-monospace,SFMono-Regular,Consolas,monospace;fill:#8da2bf;letter-spacing:1.2px}.metric{font:800 66px ui-sans-serif,system-ui;fill:#f8fafc}.metricLabel{font:700 14px ui-sans-serif,system-ui;fill:#9fb2cc;letter-spacing:1.5px}.month{font:700 11px ui-monospace,SFMono-Regular,Consolas,monospace;fill:#8194ad}.day{font:700 11px ui-monospace,SFMono-Regular,Consolas,monospace;fill:#657791}.small{font:600 10px ui-monospace,SFMono-Regular,Consolas,monospace;fill:#71849e;letter-spacing:.45px}.status{font:800 11px ui-monospace,SFMono-Regular,Consolas,monospace;fill:#70e1c1;letter-spacing:1px}.band{font:700 12px ui-monospace,SFMono-Regular,Consolas,monospace;fill:#aebed3;letter-spacing:.5px}</style>
  <rect x="4" y="4" width="712" height="812" rx="28" fill="#040711" stroke="#172033" stroke-width="8"/><rect x="10" y="10" width="700" height="800" rx="22" fill="url(#mobileBg)" stroke="url(#mobileEdge)" stroke-width="1.5"/><rect x="22" y="22" width="676" height="776" rx="17" fill="none" stroke="#26344a"/>
  <circle cx="45" cy="48" r="5" fill="#41d7b2"/><text x="60" y="52" class="status">SYNCED</text><text x="675" y="52" text-anchor="end" class="small">12-MONTH WINDOW</text><line x1="40" y1="71" x2="680" y2="71" stroke="#26344a"/>
  <text x="42" y="140" class="metric">${escapeXml(total)}</text><text x="42" y="169" class="metricLabel">REPOSITORY COMMITS</text><text x="678" y="119" text-anchor="end" class="eyebrow">SKILLAURA //</text><text x="678" y="140" text-anchor="end" class="eyebrow">ENGINEERING ACTIVITY</text><text x="678" y="164" text-anchor="end" class="small">12 PROJECTS · ALL AUTHORS + AUTOMATION</text>
  ${bandMarkup}
  <line x1="40" y1="722" x2="680" y2="722" stroke="#26344a"/><text x="42" y="762" class="small">DAILY INTENSITY</text><text x="390" y="762" text-anchor="end" class="small">LESS</text>${legend}<text x="574" y="762" class="small">MORE</text><text x="678" y="786" text-anchor="end" class="small">DATA SNAPSHOT ${escapeXml(snapshot)}</text>
  </svg>`;
}
