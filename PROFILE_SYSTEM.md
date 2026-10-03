# SkillAura profile system

## Architecture

`README.md`, `data/stats.json`, and every SVG in `assets/` are generated from `README.template.md`, the single project manifest at `data/projects.json`, and current GitHub API data. `scripts/generate-profile.mjs` performs the refresh; `scripts/validate-profile.mjs` enforces scope, security, and presentation rules.

Each manifest entry declares its repository, category, visibility, inclusion flags, display name, description, image, related repositories, attribution, and tags. The flags are the only source for deciding which projects enter statistics, language bytes, rolling activity, and the portfolio.

## Canonical metric model

The main dashboard contains only the twelve configured SkillAura projects. External professional work and forked or derived work are presented separately.

- **Stars on tracked repositories:** current sum of GitHub `stargazers_count` across projects with `includeInStats: true`.
- **Tracked commits · all time:** all commits reachable from each tracked repository's default branch, across all authors and automation accounts.
- **Pull requests:** open and closed pull requests returned by each tracked repository's pull-request collection.
- **Issues:** open and closed repository issues; pull-request records are excluded.
- **Active projects · 12 months:** tracked projects containing at least one qualifying default-branch commit in the rolling 365-day window.
- **Rolling 12-month commits:** qualifying default-branch commits dated inside that window.
- **Contribution days:** UTC calendar days inside the window with at least one qualifying tracked commit.
- **Current streak:** consecutive contribution days ending at the latest qualifying date. It is not tied to the refresh date.
- **Longest streak:** maximum consecutive contribution-day run inside the rolling window.
- **Active coverage:** active projects divided by all twelve tracked SkillAura projects, rounded to a whole percentage.

GitHub language-byte totals include only projects with `includeInLanguages: true`. They describe repository composition and are not an expertise score.

## Private-data boundary

The four configured private SkillAura projects may publish their names and safe aggregates: primary language, all-time default-branch commit count, rolling commit count, and last repository activity date. The generator never publishes private URLs, source, paths, issue or pull-request details, credentials, customer data, or infrastructure.

The generator requires `PROFILE_DATA_TOKEN`; Actions maps it from `SKILLAURA_PROFILE_TOKEN`. The value is used only in authenticated API requests and is never written or logged. Generation fails if configured private repositories cannot be read.

## Automation and idempotence

`.github/workflows/refresh-profile.yml` runs every six hours and supports manual dispatch. It generates, tests, validates, and commits only changed generated files.

`generatedAt` is retained when repository-derived data is identical to the previous snapshot. Therefore identical GitHub input produces identical output and no timestamp-only commit.

## Local verification

Set `PROFILE_DATA_TOKEN` in process memory, then run:

```bash
npm run generate
npm test
npm run validate
```

Never store the token in this repository or an environment file inside the checkout.
