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
- `assets/github-stats.svg`
- `assets/github-stats-mobile.svg`
- `assets/contribution-activity.svg`
- `assets/contribution-activity-mobile.svg`
- `assets/languages.svg`

Generated output is written only when content changes. The previous `generatedAt` value is retained when the underlying repository data is unchanged, which keeps scheduled runs idempotent.

## Metrics

All dashboard statistics use only the twelve approved SkillAura projects. Forked and external repositories are displayed separately in the profile and are excluded from these totals.

- **Total stars earned:** sum of current GitHub `stargazers_count` values.
- **Tracked commits:** total commits reachable from each repository's default branch.
- **Pull requests:** all open and closed pull requests returned by GitHub issue search with `type:pr`.
- **Issues:** all open and closed issues returned by GitHub issue search with `type:issue`; pull requests are excluded.
- **Active repositories, 12 months:** repositories with at least one default-branch commit during the rolling 365-day window.
- **Tracked contributions:** default-branch repository commits across all authors and automation accounts during that rolling window. This is repository activity, not personal contribution activity.
- **Current streak:** consecutive qualifying UTC activity days ending on the snapshot date. A gap on the snapshot date produces a zero current streak.
- **Longest streak:** longest sequence of consecutive qualifying UTC activity days inside the rolling window.
- **Active coverage ring:** active repositories divided by the twelve approved SkillAura projects, rounded to a whole percentage. It is an objective coverage ratio, not a grade or quality score.

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
