import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const required = [
  'README.md',
  'data/projects.json',
  'data/stats.json',
  'assets/activity.svg',
  'assets/languages.svg',
  '.github/workflows/refresh-profile.yml'
];
for (const file of required) {
  if (!fs.existsSync(path.join(root, file))) throw new Error(`Missing required file: ${file}`);
}

const manifest = JSON.parse(fs.readFileSync(path.join(root, 'data/projects.json'), 'utf8'));
const stats = JSON.parse(fs.readFileSync(path.join(root, 'data/stats.json'), 'utf8'));
const all = Object.values(manifest.categories).flat();

if (manifest.categories.skillAura.length !== 12) throw new Error('Expected 12 SkillAura projects');
if (manifest.categories.forked.length !== 1) throw new Error('Expected one forked project');
if (manifest.categories.external.length !== 3) throw new Error('Expected three external projects');
if (!manifest.categories.forked.some((item) => item.repository === 'Skill-Aura-Official/Hoo-Bank' && item.classification === 'forked-derived')) throw new Error('Hoo-Bank fork classification missing');
if (stats.scope.skillAuraPublicTracked !== 8) throw new Error('Expected eight public SkillAura repositories in live metrics');
if (stats.scope.externalPublicTracked !== 1) throw new Error('Expected one external public repository in live metrics');
if (all.some((item) => item.trackMetrics && item.visibility !== 'public')) throw new Error('Private repository configured for automated metrics');

const workflow = fs.readFileSync(path.join(root, '.github/workflows/refresh-profile.yml'), 'utf8');
if (!workflow.includes('contents: write')) throw new Error('Workflow cannot update generated assets');
if (/personal[_-]?access[_-]?token|gh[_-]?pat|access[_-]?token/i.test(workflow.replace(/GITHUB_TOKEN/g, ''))) throw new Error('Workflow appears to reference a personal token');

console.log('Profile validation passed.');
