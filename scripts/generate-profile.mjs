import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const root = process.cwd();
const manifest = JSON.parse(await fs.readFile(path.join(root, 'data', 'projects.json'), 'utf8'));
const token = process.env.GITHUB_TOKEN || '';
const currentYear = new Date().getUTCFullYear();
const now = new Date();

const headers = {
  Accept: 'application/vnd.github+json',
  'X-GitHub-Api-Version': '2022-11-28',
  'User-Agent': 'SkillAura-profile-refresh'
};
if (token) headers.Authorization = `Bearer ${token}`;

async function request(url) {
  const response = await fetch(url, { headers });
  if (!response.ok) throw new Error(`GitHub API ${response.status} for ${url}`);
  return response;
}

async function json(url) {
  return (await request(url)).json();
}

function pageCount(response, body) {
  const link = response.headers.get('link') || '';
  const last = link.match(/[?&]page=(\d+)>; rel="last"/);
  if (last) return Number(last[1]);
  return Array.isArray(body) ? body.length : 0;
}

async function commitCount(repository, since) {
  const query = new URLSearchParams({ per_page: '1' });
  if (since) query.set('since', since.toISOString());
  const response = await request(`https://api.github.com/repos/${repository}/commits?${query}`);
  const body = await response.json();
  return pageCount(response, body);
}

async function collect(entry) {
  const repository = entry.repository;
  const [metadata, languages, commits, yearCommits, days90, days30] = await Promise.all([
    json(`https://api.github.com/repos/${repository}`),
    json(`https://api.github.com/repos/${repository}/languages`),
    commitCount(repository),
    commitCount(repository, new Date(Date.UTC(currentYear, 0, 1))),
    commitCount(repository, new Date(now.getTime() - 90 * 86400000)),
    commitCount(repository, new Date(now.getTime() - 30 * 86400000))
  ]);
  return {
    repository,
    defaultBranch: metadata.default_branch,
    fork: metadata.fork,
    archived: metadata.archived,
    pushedAt: metadata.pushed_at,
    commits,
    currentYearCommits: yearCommits,
    commits90Days: days90,
    commits30Days: days30,
    languages
  };
}

const tracked = {};
for (const [category, entries] of Object.entries(manifest.categories)) {
  tracked[category] = [];
  for (const entry of entries.filter((item) => item.trackMetrics)) {
    tracked[category].push(await collect(entry));
  }
}

function aggregate(repositories) {
  const languages = {};
  for (const repo of repositories) {
    for (const [language, bytes] of Object.entries(repo.languages)) {
      languages[language] = (languages[language] || 0) + bytes;
    }
  }
  const latest = repositories.map((repo) => repo.pushedAt).filter(Boolean).sort().at(-1) || null;
  return {
    trackedRepositories: repositories.length,
    commits: repositories.reduce((sum, repo) => sum + repo.commits, 0),
    currentYearCommits: repositories.reduce((sum, repo) => sum + repo.currentYearCommits, 0),
    commits90Days: repositories.reduce((sum, repo) => sum + repo.commits90Days, 0),
    commits30Days: repositories.reduce((sum, repo) => sum + repo.commits30Days, 0),
    latestActivity: latest,
    languages
  };
}

const stats = {
  schemaVersion: 1,
  generatedAt: now.toISOString(),
  metricDefinition: 'Default-branch repository activity across all authors and automation accounts. These values are not personal contribution counts.',
  scope: {
    skillAuraProjects: manifest.categories.skillAura.length,
    skillAuraPublicTracked: tracked.skillAura.length,
    skillAuraPrivateNamed: manifest.categories.skillAura.filter((item) => item.visibility === 'private').length,
    forkedProjects: manifest.categories.forked.length,
    externalProjects: manifest.categories.external.length,
    externalPublicTracked: tracked.external.length
  },
  categories: {
    skillAuraPublic: aggregate(tracked.skillAura),
    forkedPublic: aggregate(tracked.forked),
    externalPublic: aggregate(tracked.external)
  },
  repositories: tracked
};

try {
  const previous = JSON.parse(await fs.readFile(path.join(root, 'data', 'stats.json'), 'utf8'));
  const { generatedAt: previousGeneratedAt, ...previousComparable } = previous;
  const { generatedAt: currentGeneratedAt, ...currentComparable } = stats;
  if (JSON.stringify(previousComparable) === JSON.stringify(currentComparable)) {
    stats.generatedAt = previousGeneratedAt;
  }
} catch {
  // The first generation has no prior snapshot to preserve.
}

function escape(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;'
  })[char]);
}

function metricCard(x, title, data, accent) {
  const latest = data.latestActivity ? data.latestActivity.slice(0, 10) : 'No activity returned';
  return `<g transform="translate(${x} 92)">
    <rect width="350" height="212" rx="18" fill="#111827" stroke="#29354b"/>
    <rect width="6" height="212" rx="3" fill="${accent}"/>
    <text x="28" y="38" class="label">${escape(title)}</text>
    <text x="28" y="83" class="value">${data.commits.toLocaleString('en-US')}</text>
    <text x="28" y="108" class="muted">default-branch commits</text>
    <text x="28" y="145" class="small">${currentYear}: ${data.currentYearCommits.toLocaleString('en-US')} · 90d: ${data.commits90Days.toLocaleString('en-US')} · 30d: ${data.commits30Days.toLocaleString('en-US')}</text>
    <text x="28" y="176" class="small">Tracked repositories: ${data.trackedRepositories}</text>
    <text x="28" y="198" class="tiny">Latest repository activity: ${escape(latest)}</text>
  </g>`;
}

const activitySvg = `<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="360" viewBox="0 0 1120 360" role="img" aria-labelledby="title description">
  <title id="title">Repository activity across approved public projects</title>
  <desc id="description">Default branch activity grouped into SkillAura, forked, and external categories.</desc>
  <style>
    .heading{font:700 24px ui-sans-serif,system-ui;fill:#f8fafc}.sub{font:400 13px ui-sans-serif,system-ui;fill:#94a3b8}.label{font:700 14px ui-sans-serif,system-ui;fill:#cbd5e1;text-transform:uppercase;letter-spacing:.7px}.value{font:800 34px ui-sans-serif,system-ui;fill:#f8fafc}.muted{font:400 12px ui-sans-serif,system-ui;fill:#94a3b8}.small{font:600 12px ui-sans-serif,system-ui;fill:#cbd5e1}.tiny{font:400 11px ui-sans-serif,system-ui;fill:#64748b}
  </style>
  <rect width="1120" height="360" rx="24" fill="#0b1120"/>
  <text x="24" y="38" class="heading">Live Engineering Activity</text>
  <text x="24" y="62" class="sub">Repository activity across all authors and automation accounts · refreshed ${escape(stats.generatedAt.slice(0, 10))} UTC</text>
  ${metricCard(24, 'Public SkillAura projects', stats.categories.skillAuraPublic, '#7c3aed')}
  ${metricCard(385, 'Forked / derived work', stats.categories.forkedPublic, '#0891b2')}
  ${metricCard(746, 'External public reference', stats.categories.externalPublic, '#059669')}
  <text x="24" y="338" class="tiny">Private repositories are named in the README but excluded from automated metrics because the workflow uses only its built-in GitHub token.</text>
</svg>`;

const palette = ['#7c3aed', '#2563eb', '#0891b2', '#059669', '#ca8a04', '#ea580c', '#db2777', '#64748b'];
const languageRows = Object.entries(stats.categories.skillAuraPublic.languages).sort((a, b) => b[1] - a[1]);
const totalBytes = languageRows.reduce((sum, [, bytes]) => sum + bytes, 0);
const top = languageRows.slice(0, 7);
const other = languageRows.slice(7).reduce((sum, [, bytes]) => sum + bytes, 0);
if (other) top.push(['Other', other]);
const bars = top.map(([language, bytes], index) => {
  const percent = totalBytes ? (bytes / totalBytes) * 100 : 0;
  const y = 94 + index * 38;
  return `<g transform="translate(28 ${y})">
    <text x="0" y="14" class="lang">${escape(language)}</text>
    <rect x="145" y="0" width="760" height="17" rx="8" fill="#1e293b"/>
    <rect x="145" y="0" width="${Math.max(3, 760 * percent / 100).toFixed(1)}" height="17" rx="8" fill="${palette[index]}"/>
    <text x="925" y="14" class="pct">${percent.toFixed(1)}%</text>
  </g>`;
}).join('');

const languageSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="430" viewBox="0 0 1120 430" role="img" aria-labelledby="title description">
  <title id="title">Language footprint across tracked public SkillAura projects</title>
  <desc id="description">GitHub language bytes aggregated across eight approved public SkillAura repositories.</desc>
  <style>
    .heading{font:700 24px ui-sans-serif,system-ui;fill:#f8fafc}.sub{font:400 13px ui-sans-serif,system-ui;fill:#94a3b8}.lang{font:600 13px ui-sans-serif,system-ui;fill:#cbd5e1}.pct{font:700 12px ui-sans-serif,system-ui;fill:#e2e8f0}.foot{font:400 11px ui-sans-serif,system-ui;fill:#64748b}
  </style>
  <rect width="1120" height="430" rx="24" fill="#0b1120"/>
  <text x="28" y="40" class="heading">Language Footprint Across Tracked Projects</text>
  <text x="28" y="64" class="sub">GitHub language statistics for ${tracked.skillAura.length} approved public SkillAura repositories</text>
  ${bars}
  <text x="28" y="405" class="foot">Repository language bytes describe code composition; they are not a rating of individual expertise.</text>
</svg>`;

async function writeIfChanged(relativePath, content) {
  const destination = path.join(root, relativePath);
  let existing = null;
  try { existing = await fs.readFile(destination, 'utf8'); } catch {}
  if (existing !== content) {
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, content, 'utf8');
  }
}

await writeIfChanged('data/stats.json', JSON.stringify(stats, null, 2) + '\n');
await writeIfChanged('assets/activity.svg', activitySvg + '\n');
await writeIfChanged('assets/languages.svg', languageSvg + '\n');
console.log('Generated profile metrics for', tracked.skillAura.length + tracked.forked.length + tracked.external.length, 'public repositories.');
