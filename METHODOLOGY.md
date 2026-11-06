# How activity is counted

The profile graphic covers the most recent 30 UTC calendar dates, including the current day up to collection time. “Private · partial” counts attributable activity visible to the authorized collector. Inaccessible repositories have unknown counts. “Unavailable” replaces the private counts if the collector cannot establish private coverage.

| Metric | Definition |
|---|---|
| Commits | Non-merge commits whose primary GitHub-linked author is Skill-Aura-Official, dated by committer time. The collector walks visible branch heads, including forks, and counts a SHA once. A SHA seen in both scopes counts publicly. A squash has a new SHA and counts separately while its original commits remain reachable. Bot commits and dashboard refreshes are excluded. |
| PRs and issues | Distinct pull requests and issues the account opened, by creation date. |
| Reviews | Distinct reviews the account submitted, by submission date. Multiple submitted reviews on one PR count separately. |

Public and private counts describe personal activity. Team activity and repository-wide totals are excluded. GitHub sets the rules and update timing for its own [native contribution graph](https://docs.github.com/en/account-and-profile/reference/profile-contributions-reference).

## Coverage and freshness

The collector inventories paginated personal, organization and collaborator repositories visible to its read credentials, deduplicating by repository ID. Separate personal and organization fine-grained credentials require read-only Metadata, Contents, Issues and Pull requests access for the approved repositories. Without those credentials the collector can scan public repositories of the configured owners only. A partial API response, rate-limit failure or unexpected loss of private coverage prevents new publication.

The [workflow](https://github.com/Skill-Aura-Official/Skill-Aura-Official/actions/workflows/refresh-profile.yml) requests collection at minutes 07, 22, 37 and 52 UTC. GitHub may start a scheduled run late. Each refresh rechecks today and the preceding two UTC dates; at least every seven days it reconciles the full window. Manual dispatch can force a full scan. Totals can change after rebases, squashes, deleted branches, visibility changes or GitHub search indexing. A timestamp older than the printed stale-after time is stale.

The collector emits a validated anonymous counter snapshot. A separate job renders one PNG, stages it in the inactive profile release slot, checks its bytes and switches the stable image URL to the verified asset. The two slots are reserved for this profile. The publication job has repository contents write and no collector credentials. Refreshes generate no Git commits. Public output contains aggregate counters and refresh times only. The previous valid display is retained on collection or staging failure. GitHub or browser caches can briefly show an earlier timestamp.
