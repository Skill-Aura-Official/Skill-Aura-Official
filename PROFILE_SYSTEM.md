# SkillAura profile system

## Architecture

`README.md`, `data/stats.json`, and every SVG in `assets/` are generated from `README.template.md`, the single project manifest at `data/projects.json`, and current GitHub API data. `scripts/generate-profile.mjs` performs the refresh; `scripts/validate-profile.mjs` enforces scope, security, and presentation rules.

Each manifest entry declares its owner, repository, category, visibility, inclusion flags, display name, description, image, related repositories, attribution, and tags. The flags are the only source for deciding which repositories enter statistics, language bytes, rolling activity, and the portfolio. The three Evisionindia repositories share the canonical `e-vms` portfolio-project identity and are each collected exactly once.

## Canonical metric model

The main dashboard covers 15 repositories: 12 SkillAura repositories plus the three approved Evisionindia external/professional repositories. The Hoo-Bank fork remains separate and is excluded from the aggregate. Evisionindia ownership stays explicit throughout the profile.

- **Stars on tracked repositories:** current sum of GitHub `stargazers_count` across projects with `includeInStats: true`.
- **Tracked commits · all time:** all commits reachable from each tracked repository's default branch, across all authors and automation accounts.
- **Pull requests:** open and closed pull requests returned by each tracked repository's pull-request collection.
- **Issues:** open and closed repository issues; pull-request records are excluded.
- **Current-year / 90-day / 30-day commits:** qualifying tracked commits dated inside the named UTC window.
- **Active repositories · 12 months:** tracked repositories containing at least one qualifying default-branch commit in the rolling 365-day window.
- **Rolling 12-month commits:** qualifying default-branch commits dated inside that window.
- **Contribution days:** UTC calendar days inside the window with at least one qualifying tracked commit.
- **Current streak:** consecutive contribution days ending at the latest qualifying date. It is not tied to the refresh date.
- **Longest streak:** maximum consecutive contribution-day run inside the rolling window.
- **Active coverage:** active repositories divided by all 15 tracked repositories, rounded to a whole percentage.

Monthly activity is stored and rendered separately for `skillAura`, `externalProfessional`, and their combined tracked total. The focused August, September, and October 2026 values are generated from the same fresh GitHub commit data.

These are repository-level metrics across all authors and automation accounts. No personal contribution count is published because no verified Git identity mapping is configured.

GitHub language-byte totals include only the 12 SkillAura projects with `includeInLanguages: true`. External Evisionindia language bytes are intentionally kept separate from that chart. The chart describes repository composition and is not an expertise score.

## Private-data boundary

The four configured private SkillAura projects may publish their names and safe aggregates: primary language, all-time default-branch commit count, rolling commit count, and last repository activity date. E-VMS publishes only an aggregate across its three approved repositories, their configured names, ownership, and safe counts. The generator never publishes private URLs, source, paths, issue or pull-request details, credentials, customer data, or infrastructure.

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
