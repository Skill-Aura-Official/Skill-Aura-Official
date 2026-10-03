import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { buildRollingWindow, renderActivityMonitor, renderActivityMonitorMobile, stabilizeGeneratedAt, sumDaily } from './activity-monitor.mjs';

const root = process.cwd();
const manifest = JSON.parse(await fs.readFile(path.join(root, 'data', 'projects.json'), 'utf8'));
const template = await fs.readFile(path.join(root, 'README.template.md'), 'utf8');
const token = process.env.PROFILE_DATA_TOKEN || '';
if (!token) throw new Error('PROFILE_DATA_TOKEN is required to refresh approved public and private repository data.');

const now = new Date();
const activityWindow = buildRollingWindow(now);
const activityStart = new Date(`${activityWindow.start}T00:00:00Z`);
const headers = {
  Accept: 'application/vnd.github+json',
  Authorization: `Bearer ${token}`,
  'X-GitHub-Api-Version': '2022-11-28',
  'User-Agent': 'SkillAura-profile-refresh'
};

async function request(url) {
  const response = await fetch(url, { headers });
  if (!response.ok) throw new Error(`GitHub API ${response.status} while refreshing approved portfolio data.`);
  return response;
}

async function json(url) {
  return (await request(url)).json();
}

async function commitsSince(fullName, since) {
  const commits = [];
  for (let page = 1; ; page += 1) {
    const query = new URLSearchParams({ per_page: '100', page: String(page), since: since.toISOString() });
    const batch = await json(`https://api.github.com/repos/${fullName}/commits?${query}`);
    commits.push(...batch);
    if (batch.length < 100) break;
  }
  return commits;
}

async function collectProject(project) {
  const fullName = `${project.owner}/${project.repository}`;
  const [metadata, languages, commits] = await Promise.all([
    json(`https://api.github.com/repos/${fullName}`),
    json(`https://api.github.com/repos/${fullName}/languages`),
    commitsSince(fullName, activityStart)
  ]);
  return {
    project,
    metadata: {
      fullName: metadata.full_name,
      visibility: metadata.visibility,
      fork: metadata.fork,
      archived: metadata.archived,
      defaultBranch: metadata.default_branch,
      primaryLanguage: metadata.language,
      pushedAt: metadata.pushed_at
    },
    languages,
    commits: commits.map((commit) => ({
      sha: commit.sha,
      date: commit.commit?.author?.date || commit.commit?.committer?.date || null
    })).filter((commit) => commit.date)
  };
}

const collected = [];
for (const project of manifest.skillAura) collected.push(await collectProject(project));

const forkMetadata = await json(`https://api.github.com/repos/${manifest.forked[0].owner}/${manifest.forked[0].repository}`);
if (!forkMetadata.fork) throw new Error('Configured derived-work repository is not reported as a GitHub fork.');

const daily = {};
const languages = {};
for (const entry of collected) {
  for (const commit of entry.commits) {
    const day = commit.date.slice(0, 10);
    daily[day] = (daily[day] || 0) + 1;
  }
  for (const [language, bytes] of Object.entries(entry.languages)) {
    languages[language] = (languages[language] || 0) + bytes;
  }
}

const publicProjects = collected
  .filter((entry) => entry.project.visibility === 'public')
  .map((entry) => ({
    repository: entry.project.repository,
    pushedAt: entry.metadata.pushedAt,
    primaryLanguage: entry.metadata.primaryLanguage
  }));

const cutoff90 = new Date(now.getTime() - 90 * 86400000).toISOString().slice(0, 10);
const cutoff30 = new Date(now.getTime() - 30 * 86400000).toISOString().slice(0, 10);
const last12MonthsActivity = sumDaily(daily, activityWindow.start, activityWindow.end);
const recent90 = sumDaily(daily, cutoff90, activityWindow.end);
const recent30 = sumDaily(daily, cutoff30, activityWindow.end);

const stats = {
  schemaVersion: 3,
  generatedAt: now.toISOString(),
  metricDefinition: 'Default-branch repository activity across all authors and automation accounts for the approved SkillAura project scope.',
  scope: {
    skillAuraProjects: manifest.skillAura.length,
    publicProjects: manifest.skillAura.filter((project) => project.visibility === 'public').length,
    privateProjects: manifest.skillAura.filter((project) => project.visibility === 'private').length,
    forkedProjects: manifest.forked.length,
    externalProjects: manifest.external.length
  },
  activity: {
    window: activityWindow,
    last12Months: last12MonthsActivity,
    last90Days: recent90,
    last30Days: recent30,
    daily: Object.fromEntries(Object.entries(daily).sort(([a], [b]) => a.localeCompare(b)))
  },
  languages: Object.fromEntries(Object.entries(languages).sort((a, b) => b[1] - a[1])),
  publicProjects
};

try {
  const previous = JSON.parse(await fs.readFile(path.join(root, 'data', 'stats.json'), 'utf8'));
  Object.assign(stats, stabilizeGeneratedAt(previous, stats));
} catch {
  // First generation has no prior snapshot.
}

function escapeXml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;'
  })[character]);
}

function escapeMarkdown(value) {
  return String(value).replace(/([\\`*_{}\[\]()#+.!|<>])/g, '\\$1');
}

function badge(label, message, color) {
  const encode = (value) => encodeURIComponent(value).replace(/-/g, '--');
  return `![${escapeMarkdown(label)}](https://img.shields.io/badge/${encode(label)}-${encode(message)}-${color}?style=for-the-badge)`;
}

function projectLink(project) {
  return project.visibility === 'public' ? `https://github.com/${project.owner}/${project.repository}` : null;
}

function tags(project) {
  return project.tags.map((tag) => `<kbd>${escapeXml(tag)}</kbd>`).join(' ');
}

function projectCard(project, options = {}) {
  const url = projectLink(project);
  const title = url ? `<a href="${url}">${escapeXml(project.repository)}</a>` : escapeXml(project.repository);
  const owner = options.showOwner ? `<sub>OWNER · ${escapeXml(project.owner)}</sub><br />` : '';
  const label = options.label || (project.visibility === 'private' ? 'PRIVATE / CLOSED SOURCE' : 'PUBLIC REPOSITORY');
  const detail = options.detail ? `<br /><sub>${escapeXml(options.detail)}</sub>` : '';
  return `<h3>${title}</h3>${owner}<sub>${escapeXml(label)}</sub><p>${escapeXml(project.description)}</p><p>${tags(project)}</p>${detail}`;
}

function cardGrid(cards) {
  const rows = [];
  for (let index = 0; index < cards.length; index += 2) {
    const left = cards[index];
    const right = cards[index + 1] || '';
    rows.push(`<tr><td width="50%" valign="top">${left}</td><td width="50%" valign="top">${right}</td></tr>`);
  }
  return `<table>${rows.join('')}</table>`;
}

function renderHero() {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="250" viewBox="0 0 1000 250" role="img" aria-labelledby="heroTitle heroDescription">
  <title id="heroTitle">SkillAura</title>
  <desc id="heroDescription">Software products, web platforms, and automation.</desc>
  <defs>
    <linearGradient id="heroBg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#070b18"/><stop offset="0.52" stop-color="#13112c"/><stop offset="1" stop-color="#071925"/></linearGradient>
    <linearGradient id="heroLine" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#38bdf8"/><stop offset="0.52" stop-color="#8b5cf6"/><stop offset="1" stop-color="#f59e0b"/></linearGradient>
    <radialGradient id="glow"><stop stop-color="#8b5cf6" stop-opacity=".28"/><stop offset="1" stop-color="#8b5cf6" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="1000" height="250" rx="24" fill="url(#heroBg)"/>
  <circle cx="158" cy="34" r="190" fill="url(#glow)"/><circle cx="860" cy="240" r="220" fill="url(#glow)"/>
  <g opacity=".35" fill="none" stroke="#334155"><path d="M0 188C190 110 280 242 480 156S810 72 1000 142"/><path d="M0 210C190 132 290 260 490 178S810 94 1000 164"/></g>
  <rect x="344" y="55" width="312" height="4" rx="2" fill="url(#heroLine)"/>
  <text x="500" y="122" text-anchor="middle" fill="#f8fafc" font-family="ui-sans-serif,system-ui" font-size="54" font-weight="800" letter-spacing="8">SKILLAURA</text>
  <text x="500" y="163" text-anchor="middle" fill="#cbd5e1" font-family="ui-sans-serif,system-ui" font-size="17" font-weight="500" letter-spacing="2">SOFTWARE PRODUCTS · WEB PLATFORMS · AUTOMATION</text>
  <text x="500" y="202" text-anchor="middle" fill="#64748b" font-family="ui-sans-serif,system-ui" font-size="12" letter-spacing="1.4">VERIFIED ENGINEERING PORTFOLIO</text>
</svg>`;
}

function renderEngineeringStats() {
  const languageCount = Object.keys(stats.languages).length;
  const cards = [
    ['12', 'APPROVED PROJECTS', 'Original SkillAura scope', '#38bdf8'],
    ['4', 'CLOSED-SOURCE', 'Approved for public naming', '#8b5cf6'],
    [String(languageCount), 'LANGUAGES DETECTED', 'GitHub language data', '#f59e0b'],
    [stats.activity.last12Months.toLocaleString('en-US'), '12M ACTIVITY', 'Default-branch commits', '#34d399']
  ];
  const groups = cards.map(([value, label, note, color], index) => {
    const x = 18 + index * 246;
    return `<g transform="translate(${x} 60)"><rect width="228" height="116" rx="16" fill="#101827" stroke="#263247"/><rect x="0" width="5" height="116" rx="3" fill="${color}"/><text x="22" y="43" class="value">${escapeXml(value)}</text><text x="22" y="70" class="label">${escapeXml(label)}</text><text x="22" y="94" class="note">${escapeXml(note)}</text></g>`;
  }).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="205" viewBox="0 0 1000 205" role="img" aria-labelledby="statsTitle statsDescription"><title id="statsTitle">SkillAura engineering snapshot</title><desc id="statsDescription">Twelve approved projects, four closed-source projects, ${Object.keys(stats.languages).length} detected languages, and ${stats.activity.last12Months} rolling twelve-month repository commits.</desc><style>.heading{font:700 19px ui-sans-serif,system-ui;fill:#f8fafc}.sub{font:400 12px ui-sans-serif,system-ui;fill:#64748b}.value{font:800 30px ui-sans-serif,system-ui;fill:#f8fafc}.label{font:700 11px ui-sans-serif,system-ui;fill:#cbd5e1;letter-spacing:.6px}.note{font:400 10px ui-sans-serif,system-ui;fill:#64748b}</style><rect width="1000" height="205" rx="22" fill="#080e1b"/><text x="20" y="32" class="heading">Engineering Snapshot</text><text x="980" y="31" text-anchor="end" class="sub">Data snapshot ${escapeXml(stats.generatedAt.slice(0, 10))} UTC</text>${groups}</svg>`;
}

function polar(cx, cy, radius, angle) {
  const radians = (angle - 90) * Math.PI / 180;
  return { x: cx + radius * Math.cos(radians), y: cy + radius * Math.sin(radians) };
}

function arc(cx, cy, radius, startAngle, endAngle) {
  const start = polar(cx, cy, radius, endAngle);
  const end = polar(cx, cy, radius, startAngle);
  const largeArc = endAngle - startAngle <= 180 ? 0 : 1;
  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 0 ${end.x} ${end.y}`;
}

function renderLanguages() {
  const entries = Object.entries(stats.languages);
  const total = entries.reduce((sum, [, bytes]) => sum + bytes, 0);
  const top = entries.slice(0, 6);
  const other = entries.slice(6).reduce((sum, [, bytes]) => sum + bytes, 0);
  if (other) top.push(['Other', other]);
  const colors = ['#38bdf8', '#8b5cf6', '#f59e0b', '#34d399', '#fb7185', '#60a5fa', '#64748b'];
  let angle = 0;
  const arcs = top.map(([language, bytes], index) => {
    const span = total ? bytes / total * 359.6 : 0;
    const shape = `<path d="${arc(205, 205, 112, angle, angle + span)}" fill="none" stroke="${colors[index]}" stroke-width="34" stroke-linecap="butt"><title>${escapeXml(language)}: ${(bytes / total * 100).toFixed(1)}%</title></path>`;
    angle += span;
    return shape;
  }).join('');
  const legend = top.map(([language, bytes], index) => {
    const x = 430 + (index % 2) * 265;
    const y = 104 + Math.floor(index / 2) * 64;
    const percent = total ? bytes / total * 100 : 0;
    return `<g transform="translate(${x} ${y})"><circle cx="7" cy="7" r="7" fill="${colors[index]}"/><text x="24" y="6" class="lang">${escapeXml(language)}</text><text x="24" y="27" class="pct">${percent.toFixed(1)}% of detected language bytes</text></g>`;
  }).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="420" viewBox="0 0 1000 420" role="img" aria-labelledby="languageTitle languageDescription"><title id="languageTitle">Language footprint across approved SkillAura projects</title><desc id="languageDescription">A donut chart derived from GitHub language bytes across all twelve approved public and private SkillAura projects.</desc><style>.heading{font:700 20px ui-sans-serif,system-ui;fill:#f8fafc}.sub{font:400 12px ui-sans-serif,system-ui;fill:#64748b}.center{font:800 42px ui-sans-serif,system-ui;fill:#f8fafc}.centerLabel{font:700 11px ui-sans-serif,system-ui;fill:#94a3b8;letter-spacing:1px}.lang{font:700 14px ui-sans-serif,system-ui;fill:#e2e8f0}.pct{font:400 11px ui-sans-serif,system-ui;fill:#64748b}</style><rect width="1000" height="420" rx="22" fill="#080e1b"/><text x="24" y="36" class="heading">Language Footprint</text><text x="24" y="58" class="sub">GitHub language data across the approved SkillAura project scope</text><circle cx="205" cy="205" r="112" fill="none" stroke="#172033" stroke-width="34"/>${arcs}<text x="205" y="199" text-anchor="middle" class="center">${entries.length}</text><text x="205" y="221" text-anchor="middle" class="centerLabel">LANGUAGES</text>${legend}<text x="430" y="368" class="sub">Aggregated portfolio composition · not an expertise rating</text></svg>`;
}

const publicByName = new Map(stats.publicProjects.map((project) => [project.repository, project]));
const publicDefinitions = manifest.skillAura.filter((project) => project.visibility === 'public');
const privateDefinitions = manifest.skillAura.filter((project) => project.visibility === 'private');
const featured = [...publicDefinitions].sort((a, b) => String(publicByName.get(b.repository)?.pushedAt || '').localeCompare(String(publicByName.get(a.repository)?.pushedAt || ''))).slice(0, 4);

const featuredCards = featured.map((project) => projectCard(project, {
  label: 'RECENT PUBLIC PROJECT',
  detail: `Latest repository activity · ${publicByName.get(project.repository)?.pushedAt?.slice(0, 10) || 'Unavailable'}`
}));
const publicCards = publicDefinitions.map((project) => projectCard(project));
const privateCards = privateDefinitions.map((project) => projectCard(project));
const forkCards = manifest.forked.map((project) => projectCard(project, { label: 'FORKED / DERIVED WORK' }));
const externalCards = manifest.external.map((project) => projectCard(project, { label: 'EXTERNAL / COLLABORATIVE', showOwner: true }));

const replacements = {
  '{{HERO_BADGES}}': [
    badge('Portfolio', `${manifest.skillAura.length} approved projects`, '7c3aed'),
    badge('Activity', 'refreshes every 6 hours', '0284c7'),
    `[![Profile refresh](https://github.com/Skill-Aura-Official/Skill-Aura-Official/actions/workflows/refresh-profile.yml/badge.svg)](https://github.com/Skill-Aura-Official/Skill-Aura-Official/actions/workflows/refresh-profile.yml)`
  ].join(' '),
  '{{PROFILE_SUMMARY}}': manifest.profile.summary,
  '{{TECHNOLOGY_BADGES}}': manifest.technologyFootprint.map((technology) => badge(technology, 'verified', '1e293b')).join(' '),
  '{{FEATURED_PROJECTS}}': cardGrid(featuredCards),
  '{{PUBLIC_PROJECTS}}': cardGrid(publicCards),
  '{{PRIVATE_PROJECTS}}': cardGrid(privateCards),
  '{{FORKED_PROJECTS}}': cardGrid(forkCards),
  '{{EXTERNAL_PROJECTS}}': cardGrid(externalCards)
};

let readme = template;
for (const [placeholder, content] of Object.entries(replacements)) readme = readme.replaceAll(placeholder, content);

async function writeIfChanged(relativePath, content) {
  const destination = path.join(root, relativePath);
  let existing = null;
  try { existing = await fs.readFile(destination, 'utf8'); } catch {}
  const normalizedExisting = existing?.replace(/\r\n/g, '\n');
  const normalizedContent = content.replace(/\r\n/g, '\n');
  if (normalizedExisting !== normalizedContent) {
    await fs.mkdir(path.dirname(destination), { recursive: true });
    await fs.writeFile(destination, normalizedContent, 'utf8');
  }
}

await writeIfChanged('README.md', readme.trimEnd() + '\n');
await writeIfChanged('assets/hero.svg', renderHero() + '\n');
await writeIfChanged('assets/engineering-stats.svg', renderEngineeringStats() + '\n');
await writeIfChanged('assets/activity.svg', renderActivityMonitor(stats) + '\n');
await writeIfChanged('assets/activity-mobile.svg', renderActivityMonitorMobile(stats) + '\n');
await writeIfChanged('assets/languages.svg', renderLanguages() + '\n');
await writeIfChanged('data/stats.json', JSON.stringify(stats, null, 2) + '\n');

console.log(`Generated SkillAura profile from ${manifest.skillAura.length} approved projects.`);
