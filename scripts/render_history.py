"""Render public Markdown solely from reconciled records and anonymous private totals."""
import argparse
import collections
import datetime as dt
import json
import re
from html import escape
from pathlib import Path

ACCOUNT = "Skill-Aura-Official"
METRICS = (
    ("commit", "Commits"), ("pr", "PRs opened"), ("issue", "Issues opened"),
    ("review", "Reviews submitted"), ("issue_comment", "Issue / PR comments"),
    ("review_comment", "Review comments"), ("release", "Releases"),
    ("discussion", "Discussions"),
)
SOURCES = {
    "commit": "reachable branch commits", "pr": "pull requests and submitted reviews",
    "review": "pull requests and submitted reviews", "issue": "issues",
    "issue_comment": "issue and PR conversation comments", "review_comment": "inline PR review comments",
    "release": "releases", "discussion": "discussion topics",
}


def figure(repos, scope, kind, value):
    selected = [r for r in repos.values() if r["private"] == (scope == "private")]
    incomplete = any(not r["scanned"] or (
        SOURCES[kind] in r.get("source_coverage", {}) and
        r["source_coverage"][SOURCES[kind]]["status"] not in ("SCANNED", "DISABLED"))
        for r in selected)
    return ("≥" + str(value) if value else "Unknown") if incomplete else str(value)


def safe(value):
    return re.sub(r"[\r\n|<>]", " ", str(value)).replace("[", "\\[").replace("]", "\\]")


def summarize(data):
    repos = {str(repo["id"]): repo for repo in data["repositories"]}
    events = {}
    for record in data["records"]:
        repo = repos[str(record["repo_id"])]
        kind = record["type"]
        if kind not in dict(METRICS):
            raise ValueError("Unrecognized activity type")
        ident = record.get("sha") if kind == "commit" else str(record["id"])
        key = kind, ident
        existing = events.get(key)
        if existing is None or not repo["private"]:
            events[key] = (record, repo)
    totals = collections.Counter()
    years = collections.defaultdict(collections.Counter)
    worked = {"public": set(), "private": set()}
    for record, repo in events.values():
        scope = "private" if repo["private"] else "public"
        totals[scope, record["type"]] += 1
        years[record["date"][:4]][scope, record["type"]] += 1
    for record in data["records"]:
        repo = repos[str(record["repo_id"])]
        worked["private" if repo["private"] else "public"].add(str(repo["id"]))
    return repos, totals, years, worked


def render(data):
    if data["account"].casefold() != ACCOUNT.casefold():
        raise ValueError("Unexpected account")
    repos, totals, years, worked = summarize(data)
    stamp = dt.datetime.fromisoformat(data["snapshot_at"].replace("Z", "+00:00"))
    coverage = data["coverage"]
    private_available = any(repo["private"] and repo["scanned"] for repo in repos.values())
    private_status = "Partial" if private_available else "Unavailable"
    lines = [
        '# <img src="https://github.com/Skill-Aura-Official.png?size=96" width="36" height="36" alt="SkillAura"> Jatin Dalal · SkillAura', "",
        "I develop E-VMS camera and recording workflows and work on CAAMOO’s conversational interface for investigating CCTV footage.",
        "", "## All-time activity", "",
        f"Snapshot {stamp:%d %b %Y, %H:%M UTC}. Coverage **{safe(coverage['status'])}**. Private coverage **{private_status}**.",
        "", "| My activity | Public | Private |", "|---|---:|---:|",
        f"| Repositories with activity | {len(worked['public'])} | {len(worked['private']) if private_available else 'Unknown'} |",
    ]
    for kind, label in METRICS:
        lines.append(f"| {label} | {figure(repos,'public',kind,totals['public',kind])} | {figure(repos,'private',kind,totals['private',kind]) if private_available else 'Unknown'} |")
    lines.extend(["", "![Attributable commits by year](assets/activity.svg)", "",
                  "[Complete public project directory](PUBLIC_PROJECTS.md) · [How activity is counted](METHODOLOGY.md)", "",
                  "## By year", ""])
    for year in sorted(years, reverse=True):
        lines.extend([f"<details><summary>{safe(year)}</summary>", "",
                      "| My activity | Public | Private |", "|---|---:|---:|"])
        for kind, label in METRICS:
            lines.append(f"| {label} | {figure(repos,'public',kind,years[year]['public',kind])} | {figure(repos,'private',kind,years[year]['private',kind]) if private_available else 'Unknown'} |")
        lines.extend(["", "</details>", ""])
    lines.extend(["## Technologies", "", "Python · JavaScript · React · SQL", ""])
    directory = ["# Complete public project directory", "",
                 f"Reconciled {stamp:%d %b %Y, %H:%M UTC}. Every discovered public repository appears below, including repositories with no attributable activity found.", ""]
    groups = collections.defaultdict(list)
    per_repo = collections.defaultdict(list)
    for record in data["records"]:
        per_repo[str(record["repo_id"])].append(record)
    for repo in repos.values():
        if repo["private"]:
            continue
        if repo["owned"] and not repo["fork"]:
            group = "Owned projects"
        elif repo["fork"] or repo["owner"].casefold() != "evisionindia":
            group = "Forks and collaborations"
        else:
            group = "Organization and professional work"
        groups[group].append(repo)
    for group in ("Owned projects", "Organization and professional work", "Forks and collaborations"):
        directory.extend(["## " + group, ""])
        for repo in sorted(groups[group], key=lambda r: r["full_name"].casefold()):
            name = repo["full_name"]
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name):
                raise ValueError("Unsafe public repository name")
            records = per_repo[str(repo["id"])]
            counts = collections.Counter()
            for kind, _ in METRICS:
                ids = {r.get("sha") if kind == "commit" else str(r["id"]) for r in records if r["type"] == kind}
                counts[kind] = len(ids)
            dates = sorted(r["date"][:10] for r in records)
            period = f"{dates[0]} to {dates[-1]}" if dates else (
                "No attributable activity found" if repo["scanned"] else "Activity unknown; scan incomplete")
            if not repo["scanned"] and dates:
                period += "; retained records from an incomplete scan"
            directory.extend([f"### [{safe(name)}](https://github.com/{name})", "",
                f"{safe(repo['relationship'])}. {'Archived. ' if repo['archived'] else ''}{period}.",
                "", " · ".join(f"{label} **{counts[kind] if repo['scanned'] else ('≥' + str(counts[kind]) if counts[kind] else 'Unknown')}**" for kind, label in METRICS), ""])
    return "\n".join(lines), "\n".join(directory)


def graphic(data):
    repos, _, years, _ = summarize(data)
    private_available = any(repo["private"] and repo["scanned"] for repo in repos.values())
    ordered = sorted(years)
    maximum = max((sum(years[y][scope, "commit"] for scope in ("public", "private")) for y in ordered), default=1) or 1
    height = 62 + 40 * len(ordered)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="360" height="{height}" viewBox="0 0 360 {height}">',
             f'<rect width="360" height="{height}" rx="8" fill="#f5f7fc"/>',
             '<g font-family="Arial,sans-serif" fill="#182437">',
             '<text x="14" y="22" font-size="15" font-weight="bold">Attributable commits by year</text>',
             '<text x="14" y="42" font-size="11">Public · blue     Private · ' +
             ('violet (partial)' if private_available else 'unavailable') + '</text>']
    for index, year in enumerate(ordered):
        y = 58 + index * 40
        public = years[year]["public", "commit"]
        private = years[year]["private", "commit"] if private_available else 0
        private_text = str(private) if private_available else "?"
        parts.extend([f'<text x="14" y="{y + 13}" font-size="13">{escape(year)}</text>',
                      f'<rect x="54" y="{y}" width="{230 * public / maximum:.2f}" height="18" rx="2" fill="#2863c5"/>',
                      f'<rect x="{54 + 230 * public / maximum:.2f}" y="{y}" width="{230 * private / maximum:.2f}" height="18" rx="2" fill="#7955b2"/>',
                      f'<text x="295" y="{y + 13}" font-size="12">{public} / {private_text}</text>'])
    return ("".join(parts) + "</g></svg>").encode()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.inventory.read_text(encoding="utf-8-sig"))
    readme, directory = render(data)
    args.output.mkdir(exist_ok=True, parents=True)
    (args.output / "README.md").write_text(readme, encoding="utf-8")
    (args.output / "PUBLIC_PROJECTS.md").write_text(directory, encoding="utf-8")
