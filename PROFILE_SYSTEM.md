# SkillAura profile system

## Purpose

This repository is the GitHub user profile for `Skill-Aura-Official`. The visitor-facing `README.md` is generated from structured project definitions and live GitHub repository data.

## Source files

- `README.template.md` contains the public presentation structure.
- `data/projects.json` is the approved project and presentation manifest.
- `scripts/generate-profile.mjs` fetches GitHub data and generates the README, statistics snapshot, and SVG assets.
- `scripts/validate-profile.mjs` verifies scope, generated files, workflow configuration, and presentation invariants.

## Generated files

- `README.md`
- `data/stats.json`
- `assets/hero.svg`
- `assets/engineering-stats.svg`
- `assets/activity.svg`
- `assets/activity-mobile.svg`
- `assets/languages.svg`

Generated output is written only when content changes. The previous `generatedAt` value is retained when the underlying repository data is unchanged, which keeps scheduled runs idempotent.

## Metrics

Activity counts default-branch commits across all authors and automation accounts for the twelve approved SkillAura projects. It is repository activity and is not described as personal contribution.

The engineering activity monitor aggregates commit-author dates by UTC day over a rolling 365-day window ending on the UTC generation date. The visual calendar includes month labels, weekday labels, daily intensity cells, an accessible tooltip per cell, a legend, and the data-snapshot timestamp. The 30-day and 90-day figures use rolling UTC cutoffs at generation time.

The snapshot timestamp advances only when repository-derived output changes. This preserves the six-hour refresh workflow without creating empty timestamp-only commits. It therefore means "data snapshot represented by this generated asset," rather than a claim of real-time streaming.

Language percentages use GitHub's language-byte API and aggregate the twelve approved SkillAura projects. Repository language data describes code composition and is not an expertise score.

Forked and external repositories remain separate from SkillAura project metrics.

## Private repository access

The generator requires `PROFILE_DATA_TOKEN`. GitHub Actions maps this variable from the encrypted repository secret `SKILLAURA_PROFILE_TOKEN`.

The credential must be able to read the four approved private SkillAura repositories. It is used only for authenticated GitHub API requests and is never written to generated output or logged by the generator. The workflow's built-in GitHub token remains responsible for committing generated changes to this profile repository.

If the secret is unavailable or cannot read the approved scope, generation fails instead of publishing partial public-only metrics.

## Automation

`.github/workflows/refresh-profile.yml` runs every six hours and supports manual dispatch. It:

1. checks out the profile repository;
2. sets up Node.js;
3. generates live profile data;
4. validates the output;
5. commits only when generated files changed.

Workflow permissions are limited to repository contents write access, which is required for automated refresh commits.

## Local refresh

Set `PROFILE_DATA_TOKEN` in process memory and run:

```bash
npm run generate
npm run validate
```

Do not place the credential in this repository or in an environment file within the checkout.

## Troubleshooting

- **Missing token:** configure `SKILLAURA_PROFILE_TOKEN` in repository Actions secrets.
- **API authorization failure:** verify that the secret can read every approved private repository.
- **No commit after a scheduled run:** this is expected when the underlying data has not changed.
- **Scope validation failure:** reconcile `data/projects.json` with the approved portfolio scope before regenerating.
