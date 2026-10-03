import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const required = [
  'README.md',
  'README.template.md',
  'PROFILE_SYSTEM.md',
  'data/projects.json',
  'data/stats.json',
  'assets/hero.svg',
  'assets/engineering-stats.svg',
  'assets/activity.svg',
  'assets/activity-mobile.svg',
  'assets/languages.svg',
  'scripts/generate-profile.mjs',
  'scripts/activity-monitor.mjs',
  'tests/activity-monitor.test.mjs',
  '.github/workflows/refresh-profile.yml'
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
if (manifest.forked.length !== 1) throw new Error('Expected one forked project');
if (manifest.external.length !== 3) throw new Error('Expected three external projects');
if (stats.scope.skillAuraProjects !== 12 || stats.scope.privateProjects !== 4) throw new Error('Generated scope does not match the manifest');
if (stats.schemaVersion !== 3) throw new Error('Expected rolling-activity schema version 3');
if (!stats.activity.window?.start || !stats.activity.window?.end) throw new Error('Rolling activity window is missing');
if (!Number.isInteger(stats.activity.last12Months)) throw new Error('Rolling twelve-month activity total is missing');
if (!Object.keys(stats.languages).length) throw new Error('Generated language data is empty');
if (!Object.keys(stats.activity.daily).length) throw new Error('Generated activity data is empty');
if (/\{\{[A-Z_]+\}\}/.test(readme)) throw new Error('README contains an unresolved template placeholder');
if (/Data and Refresh Policy|Repository Audit|Evidence Classification|Token Policy/i.test(readme)) throw new Error('README contains internal system documentation');
if (/https:\/\/github\.com\/Skill-Aura-Official\/(kiru|SSB|nyther-userbot|TenderIQ)/i.test(readme)) throw new Error('README exposes a private repository URL');
if (!readme.includes('Forked / Derived Work')) throw new Error('Forked work section missing');
if (!readme.includes('Selected External / Collaborative Work')) throw new Error('External work section missing');
if (!workflow.includes('cron: "17 */6 * * *"')) throw new Error('Workflow is not scheduled every six hours');
if (!workflow.includes('PROFILE_DATA_TOKEN: ${{ secrets.SKILLAURA_PROFILE_TOKEN }}')) throw new Error('Workflow private-repository credential mapping missing');
if (!workflow.includes('contents: write')) throw new Error('Workflow cannot update generated content');
if (!workflow.includes('run: npm test')) throw new Error('Workflow does not execute activity-monitor regression tests');

for (const svg of ['hero.svg', 'engineering-stats.svg', 'activity.svg', 'activity-mobile.svg', 'languages.svg']) {
  const content = fs.readFileSync(path.join(root, 'assets', svg), 'utf8');
  if (!content.startsWith('<svg') || !content.includes('</svg>')) throw new Error(`Invalid SVG structure: ${svg}`);
  if (!content.includes('<title') || !content.includes('<desc')) throw new Error(`SVG accessibility text missing: ${svg}`);
}

const activitySvg = fs.readFileSync(path.join(root, 'assets/activity.svg'), 'utf8');
const mobileActivitySvg = fs.readFileSync(path.join(root, 'assets/activity-mobile.svg'), 'utf8');
for (const marker of ['ENGINEERING ACTIVITY MONITOR', 'ROLLING 12-MONTH WINDOW', 'REPOSITORY COMMITS', 'DATA SNAPSHOT', 'DAILY INTENSITY', 'SYNCED']) {
  if (!activitySvg.includes(marker)) throw new Error(`Activity monitor marker missing: ${marker}`);
}
for (const weekday of ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']) {
  if (!activitySvg.includes(`>${weekday}<`)) throw new Error(`Activity monitor weekday missing: ${weekday}`);
}
if (/PUBLIC SKILLAURA PROJECTS|EXTERNAL PUBLIC REFERENCE/i.test(activitySvg)) throw new Error('Legacy activity-card design remains in the primary monitor');
if (!readme.includes('<source media="(max-width: 600px)" srcset="./assets/activity-mobile.svg">')) throw new Error('Responsive narrow-screen activity asset is not wired into the README');
if (!mobileActivitySvg.includes('ENGINEERING ACTIVITY') || !mobileActivitySvg.includes('DATA SNAPSHOT')) throw new Error('Mobile activity monitor content is incomplete');

const repositoryText = required.concat(['package.json', '.gitignore']).map((file) => fs.readFileSync(path.join(root, file), 'utf8')).join('\n');
if (/gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----/.test(repositoryText)) throw new Error('Potential credential material detected');

const publicScopeFiles = [
  'README.md', 'README.template.md', 'PROFILE_SYSTEM.md', 'data/projects.json', 'data/stats.json',
  'assets/hero.svg', 'assets/engineering-stats.svg', 'assets/activity.svg', 'assets/activity-mobile.svg', 'assets/languages.svg',
  'scripts/generate-profile.mjs', 'scripts/activity-monitor.mjs', '.github/workflows/refresh-profile.yml'
];
const trackedText = publicScopeFiles.map((file) => fs.readFileSync(path.join(root, file), 'utf8')).join('\n');
const excludedNames = ['YXVyb3JhLWluay1nZW5pZQ==', 'dHV0b3I=', 'Vk1TLUFJLUFuYWx5dGljcw==', 'Y2N0di12bXMxMA=='].map((value) => Buffer.from(value, 'base64').toString('utf8'));
for (const excluded of excludedNames) {
  if (trackedText.includes(excluded)) throw new Error(`Excluded repository reference found: ${excluded}`);
}
const restrictedInnovathonName = Buffer.from('SW5ub3ZhdGhvbg==', 'base64').toString('utf8');
const isolatedRestrictedName = new RegExp(`(^|[^-\\w])${restrictedInnovathonName}([^\\w-]|$)`, 'm');
if (isolatedRestrictedName.test(trackedText.replaceAll('Innovathon-Public', ''))) throw new Error('Excluded private repository reference found');

console.log('SkillAura profile validation passed.');
