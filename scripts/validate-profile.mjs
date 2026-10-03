import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const generatedSvgs = [
  'assets/hero.svg', 'assets/github-stats.svg', 'assets/github-stats-mobile.svg',
  'assets/contribution-activity.svg', 'assets/contribution-activity-mobile.svg', 'assets/languages.svg'
];
const required = [
  'README.md', 'README.template.md', 'PROFILE_SYSTEM.md', 'data/projects.json', 'data/stats.json',
  ...generatedSvgs, 'scripts/generate-profile.mjs', 'scripts/github-stats.mjs',
  'tests/github-stats.test.mjs', '.github/workflows/refresh-profile.yml'
];
for (const file of required) {
  if (!fs.existsSync(path.join(root, file))) throw new Error(`Missing required file: ${file}`);
}

const manifest = JSON.parse(fs.readFileSync(path.join(root, 'data/projects.json'), 'utf8'));
const stats = JSON.parse(fs.readFileSync(path.join(root, 'data/stats.json'), 'utf8'));
const readme = fs.readFileSync(path.join(root, 'README.md'), 'utf8');
const workflow = fs.readFileSync(path.join(root, '.github/workflows/refresh-profile.yml'), 'utf8');

if (manifest.skillAura.length !== 12) throw new Error('Expected twelve approved SkillAura projects');
if (manifest.skillAura.filter((project) => project.visibility === 'public').length !== 8) throw new Error('Expected eight public SkillAura projects');
if (manifest.skillAura.filter((project) => project.visibility === 'private').length !== 4) throw new Error('Expected four private SkillAura projects');
if (manifest.forked.length !== 1 || manifest.external.length !== 3) throw new Error('Forked or external scope mismatch');
if (stats.schemaVersion !== 4) throw new Error('Expected GitHub-stats schema version 4');
if (stats.scope.skillAuraProjects !== 12 || stats.scope.privateProjects !== 4) throw new Error('Generated scope does not match manifest');
for (const metric of ['totalStars', 'totalCommits', 'totalPullRequests', 'totalIssues', 'contributedRepositoriesLastYear']) {
  if (!Number.isInteger(stats.githubStats?.[metric]) || stats.githubStats[metric] < 0) throw new Error(`Invalid GitHub metric: ${metric}`);
}
for (const metric of ['totalTrackedContributions', 'currentStreak', 'longestStreak']) {
  if (!Number.isInteger(stats.contributionActivity?.[metric]) || stats.contributionActivity[metric] < 0) throw new Error(`Invalid contribution metric: ${metric}`);
}
if (!stats.activity.window?.start || !stats.activity.window?.end) throw new Error('Rolling activity window is missing');
if (!Object.keys(stats.languages).length || !Object.keys(stats.activity.daily).length) throw new Error('Generated repository data is empty');
if (/\{\{[A-Z_]+\}\}/.test(readme)) throw new Error('README contains an unresolved template placeholder');
if (/Data and Refresh Policy|Repository Audit|Evidence Classification|Token Policy/i.test(readme)) throw new Error('README contains internal documentation');
if (/https:\/\/github\.com\/Skill-Aura-Official\/(kiru|SSB|nyther-userbot|TenderIQ)/i.test(readme)) throw new Error('README exposes a private repository URL');
if (!readme.includes('GitHub Stats') || !readme.includes('Contribution Activity')) throw new Error('Primary stats sections missing');
if (!readme.includes('Forked / Derived Work') || !readme.includes('Selected External / Collaborative Work')) throw new Error('Portfolio classification sections missing');
if (!readme.includes('./assets/github-stats-mobile.svg') || !readme.includes('./assets/contribution-activity-mobile.svg')) throw new Error('Responsive stats assets missing from README');
if (/assets\/activity(?:-mobile)?\.svg|Engineering Activity Monitor/.test(readme)) throw new Error('Superseded heatmap presentation remains in README');

if (!workflow.includes('cron: "17 */6 * * *"') || !workflow.includes('workflow_dispatch:')) throw new Error('Six-hour/manual refresh configuration missing');
if (!workflow.includes('PROFILE_DATA_TOKEN: ${{ secrets.SKILLAURA_PROFILE_TOKEN }}')) throw new Error('Private-repository credential mapping missing');
if (!workflow.includes('contents: write') || !workflow.includes('run: npm test')) throw new Error('Workflow permissions or tests missing');

for (const relative of generatedSvgs) {
  const content = fs.readFileSync(path.join(root, relative), 'utf8');
  if (!content.startsWith('<svg') || !content.includes('</svg>')) throw new Error(`Invalid SVG structure: ${relative}`);
  if (!content.includes('<title') || !content.includes('<desc')) throw new Error(`SVG accessibility text missing: ${relative}`);
}
const statsSvg = fs.readFileSync(path.join(root, 'assets/github-stats.svg'), 'utf8');
for (const marker of ['GitHub Stats', 'TOTAL STARS EARNED', 'TRACKED COMMITS', 'PULL REQUESTS', 'ISSUES', 'ACTIVE REPOSITORIES', 'ACTIVE COVERAGE', 'SYNCED']) {
  if (!statsSvg.includes(marker)) throw new Error(`GitHub stats marker missing: ${marker}`);
}
const contributionSvg = fs.readFileSync(path.join(root, 'assets/contribution-activity.svg'), 'utf8');
for (const marker of ['Contribution Activity', 'TRACKED CONTRIBUTIONS', 'CURRENT STREAK', 'LONGEST STREAK']) {
  if (!contributionSvg.includes(marker)) throw new Error(`Contribution marker missing: ${marker}`);
}

const repositoryText = required.concat(['package.json', '.gitignore']).map((file) => fs.readFileSync(path.join(root, file), 'utf8')).join('\n');
if (/gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----/.test(repositoryText)) throw new Error('Potential credential material detected');
const excludedNames = ['YXVyb3JhLWluay1nZW5pZQ==', 'dHV0b3I=', 'Vk1TLUFJLUFuYWx5dGljcw==', 'Y2N0di12bXMxMA=='].map((value) => Buffer.from(value, 'base64').toString('utf8'));
for (const excluded of excludedNames) {
  if (repositoryText.includes(excluded)) throw new Error(`Excluded repository reference found: ${excluded}`);
}
const restrictedName = Buffer.from('SW5ub3ZhdGhvbg==', 'base64').toString('utf8');
const isolatedRestrictedName = new RegExp(`(^|[^-\\w])${restrictedName}([^\\w-]|$)`, 'm');
if (isolatedRestrictedName.test(repositoryText.replaceAll('Innovathon-Public', ''))) throw new Error('Excluded private repository reference found');

console.log('SkillAura profile validation passed.');
