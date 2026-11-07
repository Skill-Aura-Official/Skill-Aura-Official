"""Render public Markdown solely from reconciled records and anonymous private totals."""
import argparse
import collections
import datetime as dt
import json
import re
import textwrap
from html import escape
from pathlib import Path

from technologies import public_rows

ACCOUNT = "Skill-Aura-Official"
HEADLINE = "Jatin Dalal · Software, AI & Automation"
INTRODUCTION = (
    "I build software and web applications, from SkillAura’s career tools and hackathon platform "
    "to community bots and workflow automation. I work across web interfaces, backend integrations, "
    "and developer tooling. My public projects include personal builds and community work, and I "
    "contribute to team-owned products at E-Vision India. My current work there covers video management, "
    "plate recognition, and AI-assisted investigations. I like taking a workflow from an early prototype "
    "through the details that make it usable and easier to verify."
)
# Copy explicitly approved for the public profile. Keep private inventory
# records out of this rendering path.
CLOSED_SOURCE = (
    ("E-VMS", "E-Vision India’s video-management product. I contribute to camera, recording, playback and operator workflows.", "E-Vision India", "https://github.com/Evisionindia/EVMS-website"),
    ("CAAMOO", "A conversational CCTV investigation application. Ishika leads CAAMOO and its training work. I contribute to the web and investigation interface.", "E-Vision India", None),
    ("ANPR", "A plate-recognition application for reviewing vehicle observations. I contribute to plate review, evidence and integration workflows.", "Personal repository and E-Vision integration", "https://github.com/Skill-Aura-Official/ANPR"),
    ("Innovathon", "SkillAura’s hackathon platform. I worked on the event web experience.", "SkillAura", "https://github.com/Skill-Aura-Official/Innovathon-Public"),
    ("Age of Telegram · Empire RPG", "A text-based RPG bot for Telegram groups. I contributed to its bot code.", "Personal repository for a community game", "https://github.com/Skill-Aura-Official/EmpireRPG_Bot"),
    ("Aurora Ink Genie", "I contributed to the React web prototype and iterated on its interface.", "Personal repository", None),
    ("Beauty and wellness website", "I contributed to a service catalogue, campaign pages and administration workflows for a beauty and wellness website.", "Customer project contribution", None),
    ("Nyther", "I contributed to a Telegram automation project with userbot deployment and management workflows.", "The Sovereign Brotherhood community", None),
    ("Kiru", "I contributed to the web application for an AI-assisted recruitment project, including application and hiring workflows.", "Personal repository", None),
    ("Nexus VMS", "I contributed to an earlier E-Vision India video-management codebase and its engineering workflow.", "E-Vision India", None),
)
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
        '<picture><source media="(max-width: 600px)" srcset="assets/hero-mobile.svg"><img src="assets/hero.svg" alt="SkillAura — software products, web platforms and automation" width="100%"></picture>', "",
        "# " + HEADLINE, "",
        INTRODUCTION, "",
        "### Work at a glance", "",
        "- **💻 Web products** · [SkillAura PathFinder AI](https://github.com/Skill-Aura-Official/SkillAura-Pathfinder) and [Innovathon](https://github.com/Skill-Aura-Official/Innovathon-Public)",
        "- **🤖 Bots and communities** · [Anisha](https://github.com/Skill-Aura-Official/Anisha) and [Empire RPG](https://github.com/Skill-Aura-Official/EmpireRPG_Bot)",
        "- **🧰 Developer tools and automation** · [Portfolio collection and attribution](METHODOLOGY.md)",
        "- **🎥 Video systems and AI** · Camera, recording, plate review and investigation workflows",
        "", "## Personal engineering history", "",
        f"Snapshot {stamp:%d %b %Y, %H:%M UTC}. Coverage **{safe(coverage['status'])}**. Private coverage **{private_status}**.",
        "",
        '<picture><source media="(max-width: 600px)" srcset="assets/activity-mobile.svg"><img src="assets/activity.svg" alt="All-time personal activity, with public and private counts" width="100%"></picture>', "",
        '<details><summary>Read the activity figures as text</summary>', "",
        "| My activity | Public | Private |", "|---|---:|---:|",
        f"| Repositories with activity | {len(worked['public'])} | {len(worked['private']) if private_available else 'Unknown'} |",
    ]
    for kind, label in METRICS:
        lines.append(f"| {label} | {figure(repos,'public',kind,totals['public',kind])} | {figure(repos,'private',kind,totals['private',kind]) if private_available else 'Unknown'} |")
    lines.extend(["", "</details>", "",
                  '<picture><source media="(max-width: 600px)" srcset="assets/timeline-mobile.svg"><img src="assets/timeline.svg" alt="Personal commit history by year and month" width="100%"></picture>', "",
                  "[Complete public project directory](PUBLIC_PROJECTS.md) · [How activity is counted](METHODOLOGY.md)", "",
                  "<details><summary>Explore every year</summary>", ""])
    for year in sorted(years, reverse=True):
        lines.extend([f"<details><summary>{safe(year)}</summary>", "",
                      "| My activity | Public | Private |", "|---|---:|---:|"])
        for kind, label in METRICS:
            lines.append(f"| {label} | {figure(repos,'public',kind,years[year]['public',kind])} | {figure(repos,'private',kind,years[year]['private',kind]) if private_available else 'Unknown'} |")
        lines.extend(["", "</details>", ""])
    lines.extend(["</details>", "", "## Private / Closed-source Projects", "",
                  "These entries cover work I can describe publicly. Linked titles open public project pages or case studies.", ""])
    for name, summary, attribution, url in CLOSED_SOURCE:
        label = f"[{name}]({url})" if url else name
        lines.append(f"- **{label}** · *{attribution}* · {summary}")
    lines.extend(["", "## Complete public projects", "",
        "Every discovered public repository is included below. Activity reflects my account-linked work.", "",
        '<picture><source media="(max-width: 600px)" srcset="assets/projects-mobile.svg"><img src="assets/projects.svg" alt="Complete public repository inventory" width="100%"></picture>', "",
        '<details><summary>Open every repository link</summary>', ""])

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
        lines.extend([f"**{group} · {len(groups[group])}**", ""])
        for repo in sorted(groups[group], key=lambda r: r["full_name"].casefold()):
            name = repo["full_name"]
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name):
                raise ValueError("Unsafe public repository name")
            lines.append(f"- [{safe(name)}](https://github.com/{name}) · {safe(repo['relationship'])}")
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
            metadata = " · ".join(x for x in [
                safe(repo.get("language") or ""), f"{repo.get('stars',0)} stars" if 'stars' in repo else "",
                f"{repo.get('forks',0)} forks" if 'forks' in repo else ""] if x)
            directory.extend([f"### [{safe(name)}](https://github.com/{name})", "",
                safe(repo.get("description") or ""), metadata, "",
                f"{safe(repo['relationship'])}. {'Archived. ' if repo['archived'] else ''}{period}.",
                "", " · ".join(f"{label} **{counts[kind] if repo['scanned'] else ('≥' + str(counts[kind]) if counts[kind] else 'Unknown')}**" for kind, label in METRICS), ""])
        lines.append("")
    lines.extend(["</details>", "", "[Open the full repository metrics and activity index](PUBLIC_PROJECTS.md)", "",
                  "## Technologies", "",
                  "Technologies verified in project source and configuration across my portfolio.", ""])
    lines.extend(["\n\n".join(public_rows(data.get("technology_inventory"))), ""])
    directory.extend(["## Personal activity by month", "",
                      "| Month | Public commits | Private commits |",
                      "|---|---:|---:|"])
    monthly=collections.defaultdict(lambda: collections.defaultdict(set))
    public_shas={r.get("sha") or r["id"] for r in data["records"] if r["type"]=="commit" and not repos[str(r["repo_id"])]["private"]}
    for row in data["records"]:
        if row["type"]!="commit":continue
        sha=row.get("sha") or row["id"]
        scope="public" if sha in public_shas else "private"
        monthly[row["date"][:7]][scope].add(sha)
    for month in sorted(monthly,reverse=True):
        directory.append(f"| {month} | {figure(repos,'public','commit',len(monthly[month]['public']))} | {figure(repos,'private','commit',len(monthly[month]['private']))} |")
    return "\n".join(lines), "\n".join(directory)


def svg_start(width, height, title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img"><title>{escape(title)}</title>',
            '<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#07111f"/><stop offset="1" stop-color="#17172e"/></linearGradient></defs>',
            f'<rect width="{width}" height="{height}" rx="18" fill="url(#bg)"/>']


def svg_text(x,y,text,size=16,color="#c6d4e5",weight=400):
    return f'<text x="{x}" y="{y}" font-family="Arial,sans-serif" font-size="{size}" fill="{color}" font-weight="{weight}">{escape(str(text))}</text>'


def graphic(data, mobile=False):
    repos,totals,years,worked=summarize(data)
    width=360 if mobile else 1100
    columns=2 if mobile else 4
    card_width=(width-36-(columns-1)*12)/columns
    metrics=[("Repositories",len(worked["public"]),len(worked["private"]),None)]
    metrics.extend((label,totals["public",kind],totals["private",kind],kind) for kind,label in METRICS if kind not in ("issue_comment","review_comment"))
    metrics.insert(5,("Comments",sum(totals["public",k] for k in ("issue_comment","review_comment")),
                     sum(totals["private",k] for k in ("issue_comment","review_comment")),"issue_comment"))
    rows=(len(metrics)+columns-1)//columns
    parts=svg_start(width,58+rows*112,"All-time attributable personal activity")
    parts.append(svg_text(18,29,"ALL-TIME PERSONAL ACTIVITY",13,"#79d5fa",700))
    for i,(label,pub,private,kind) in enumerate(metrics):
        x=18+(i%columns)*(card_width+12)
        y=48+(i//columns)*112
        public_text=figure(repos,"public",kind,pub) if kind else str(pub)
        private_text=figure(repos,"private",kind,private) if kind else str(private)
        parts.extend([f'<rect x="{x}" y="{y}" width="{card_width}" height="100" rx="10" fill="#101f32" stroke="#2b3c55"/>',
                      svg_text(x+12,y+23,label,13,"#bfcddd",600),
                      svg_text(x+12,y+54,public_text,25,"#73d3fa",700),
                      svg_text(x+card_width/2+8,y+54,private_text,25,"#b6a2fa",700),
                      svg_text(x+12,y+80,"Public",12),
                      svg_text(x+card_width/2+8,y+80,"Private",12)])
    return ("".join(parts)+"</svg>").encode()


def timeline(data,mobile=False):
    repos,_,years,_=summarize(data)
    width=360 if mobile else 1100
    months=collections.defaultdict(set)
    for row in data["records"]:
        if row["type"]=="commit":
            months[row["date"][:7]].add(row.get("sha") or row["id"])
    ordered=[]
    if months:
        first=min(months)
        last=max(months)
        year,month=map(int,first.split("-"))
        while f"{year:04}-{month:02}"<=last:
            ordered.append(f"{year:04}-{month:02}")
            month+=1
            if month==13:year,month=year+1,1
    year_height=42*len(years)+62
    height=year_height+225
    parts=svg_start(width,height,"Personal commits by year and calendar month")
    parts.append(svg_text(18,28,"COMMIT HISTORY",13,"#79d5fa",700))
    maximum=max([sum(years[y][s,"commit"] for s in ("public","private")) for y in years] or [1]) or 1
    bar_width=width-180
    for i,year in enumerate(sorted(years)):
        y=54+i*42
        public=years[year]["public","commit"]
        private=years[year]["private","commit"]
        parts.extend([svg_text(18,y+15,year,14),
            f'<rect x="66" y="{y}" width="{bar_width*public/maximum:.2f}" height="20" fill="#48bce9"/>',
            f'<rect x="{66+bar_width*public/maximum:.2f}" y="{y}" width="{bar_width*private/maximum:.2f}" height="20" fill="#9a7de8"/>',
            svg_text(width-99,y+15,f"{figure(repos,'public','commit',public)} / {figure(repos,'private','commit',private)}",12)])
    parts.append(svg_text(18,year_height+14,"Public / private · coverage partial",12))
    parts.append(svg_text(18,year_height+44,"MONTHLY COMMITS",12,"#79d5fa",700))
    max_count=max([len(months[m]) for m in ordered] or [1]) or 1
    step=(width-36)/max(len(ordered),1)
    for i,month in enumerate(ordered):
        value=len(months[month])
        h=100*value/max_count
        x=18+i*step
        parts.append(f'<rect x="{x:.2f}" y="{year_height+155-h:.2f}" width="{max(step-4,1):.2f}" height="{h:.2f}" rx="2" fill="#48bce9"><title>{month}: {value} commits</title></rect>')
        if i in (0,len(ordered)-1) or not mobile:
            parts.append(svg_text(x,year_height+176,month[2:],9))
    parts.append(svg_text(18,height-15,"Every available year. Monthly details in the public index.",11))
    return ("".join(parts)+"</svg>").encode()


def artwork(data):
    return {"assets/activity.svg":graphic(data),"assets/activity-mobile.svg":graphic(data,True),
            "assets/timeline.svg":timeline(data),"assets/timeline-mobile.svg":timeline(data,True),
            "assets/projects.svg":project_graphic(data),"assets/projects-mobile.svg":project_graphic(data,True)}


def project_graphic(data,mobile=False):
    repos=sorted((r for r in data["repositories"] if not r["private"]),key=lambda r:r["full_name"].casefold())
    width=360 if mobile else 1100
    columns=1 if mobile else 2
    rows=(len(repos)+columns-1)//columns
    card_width=(width-36-(columns-1)*16)/columns
    parts=svg_start(width,58+rows*150,"Every discovered public project")
    parts.append(svg_text(18,29,f"PUBLIC PROJECTS · {len(repos)} REPOSITORIES",13,"#79d5fa",700))
    for i,repo in enumerate(repos):
        x=18+(i%columns)*(card_width+16)
        y=48+(i//columns)*150
        name=repo["full_name"].split("/",1)[-1]
        desc=repo.get("description") or repo["relationship"].capitalize()+" repository"
        desc_lines=textwrap.wrap(desc,width=41 if mobile else 66)[:2]
        count=len({r.get("sha") or r["id"] for r in data["records"] if str(r["repo_id"])==str(repo["id"]) and r["type"]=="commit"})
        parts.append(f'<rect x="{x}" y="{y}" width="{card_width}" height="138" rx="12" fill="#101f32" stroke="#2b3c55"/>')
        parts.append(svg_text(x+14,y+26,name[:38],16,"#f4f7ff",700))
        parts.append(svg_text(x+14,y+47,repo["owner"],12,"#79d5fa"))
        for n,line in enumerate(desc_lines):
            parts.append(svg_text(x+14,y+71+n*17,line,12))
        details=[repo.get("language") or "",f"{count} personal commits" if repo["scanned"] else "Activity partially available"]
        parts.append(svg_text(x+14,y+118," · ".join(v for v in details if v),12,"#b6a2fa"))
    return ("".join(parts)+"</svg>").encode()


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
