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
  'assets/languages.svg',
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

for (const svg of ['hero.svg', 'engineering-stats.svg', 'activity.svg', 'languages.svg']) {
  const content = fs.readFileSync(path.join(root, 'assets', svg), 'utf8');
  if (!content.startsWith('<svg') || !content.includes('</svg>')) throw new Error(`Invalid SVG structure: ${svg}`);
  if (!content.includes('<title') || !content.includes('<desc')) throw new Error(`SVG accessibility text missing: ${svg}`);
}

const repositoryText = required.concat(['package.json', '.gitignore']).map((file) => fs.readFileSync(path.join(root, file), 'utf8')).join('\n');
if (/gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----/.test(repositoryText)) throw new Error('Potential credential material detected');

console.log('SkillAura profile validation passed.');
