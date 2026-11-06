# How the complete work history is counted

This custom inventory covers all retrievable event dates and reachable attributable commit history, including commits that predate account creation. It is separate from GitHub's native contribution calendar. Accessible repositories and current reachable branch history cannot reconstruct deleted repositories, deleted comments, unreachable commits, or activity that GitHub will not expose to the authorized collector. Coverage is labelled partial whenever those limits apply.

## What the figures mean

The public profile shows account-wide attributable activity, with public totals and anonymous private totals separately. It also links every discovered public repository. The private owner report holds the actual authorized names, branches, dates and event records. Accessible repositories with no attributable event remain in the owner directory.

| Metric | Definition |
|---|---|
| Repositories with activity | Distinct stable repository IDs with an attributable record. Ownership alone is insufficient. Commits linked to another account or without verified authorship are not reassigned merely because the repository is accessible. |
| Commits | GitHub-linked primary authors and credited co-authors, across reachable branches. A SHA counts once account-wide. Each repository/branch membership remains inspectable privately. |
| PRs and issues | Distinct items opened by the verified account. |
| Reviews | Distinct submitted reviews, including multiple submissions on the same PR. |
| Issue / PR comments | Individual comments written by the account, kept separate from issues and PRs. |
| Review comments | Individual inline review comments, separate from submitted reviews. |
| Releases and discussions | Attributable records exposed by the authorized source, with unsupported or denied sources recorded as coverage gaps. |

The account-wide commit total deduplicates identical SHAs across forks and branches. A SHA visible in both public and private repositories counts publicly. Per-repository commit totals may therefore sum to more than the account-wide figure. Cherry-picks and squash merges have different SHAs and remain distinct objects when both are reachable. Year tables use the record's event timestamp. Authored and committed timestamps are retained separately for commits.

## Discovery and coverage

The collector combines paginated personal, organization and collaboration inventories with contribution discovery and date-split search queries. Stable IDs join renamed repositories. Archived projects and forks remain eligible. Source receipts in the private inventory record date ranges, access results and scanning outcomes. A failed source preserves previous known records and records its gap. Unknown coverage does not become zero.

Detailed record exports stay in the private history repository and the authenticated Windows report. The public profile, directory and graphic expose public project information and anonymous private aggregates. Private names, branch names, links, SHAs, titles and raw API payloads do not belong in public output.

## Refresh and publication

One Actions workflow requests refresh at minutes 07, 22, 37 and 52 UTC. GitHub may start scheduled jobs late. The initial run backfills history. Incremental runs use the saved private checkpoint, overlapping queries and SHA/event deduplication. Periodic full reconciliation revisits older records.

The public README contains native Markdown numbers and the dataset snapshot date. The graphic supplements those numbers. A public snapshot commit is created only when the represented data changes. Timestamp-only refreshes create no public commit. Automated snapshot commits are labelled explicitly and excluded from engineering activity. Collector code repairs requested by the owner remain normal engineering changes.

Private checkpoints and exports are published to an access-controlled repository. Public files are derived separately from the inventory. Failure preserves the last published snapshot. Last attempted and successful refreshes can be checked independently from the dataset snapshot, in workflow metadata and the private report. A successful workflow badge alone does not establish freshness.

[Refresh workflow](https://github.com/Skill-Aura-Official/Skill-Aura-Official/actions/workflows/refresh-profile.yml)
