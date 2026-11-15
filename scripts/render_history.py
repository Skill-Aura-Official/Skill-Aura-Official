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
    "Hi, I’m Jatin. I build web applications, AI interfaces, community bots and automation. "
    "Through SkillAura, I work on career tools and hackathon experiences; my other projects span "
    "backend integrations, developer tooling and community work.\n\n"
    "At E-Vision India, I contribute to team-owned products for video management, plate recognition "
    "and AI-assisted investigations. I enjoy connecting the interface to what happens behind it: "
    "the data, permissions and integrations that make a workflow useful. This profile brings together "
    "my personal projects and contributions, with ownership and team credits kept visible."
)
# Copy explicitly approved for the public profile. Keep private inventory
# records out of this rendering path.
CLOSED_SOURCE = (
    ("WebGuide AI", "Voice-assisted website guidance for blind and low-vision users. I contribute to its development. Riya Yadav owns and leads the project.", "Owner and lead: Riya Yadav · Development contributor: Jatin Dalal", "https://webguide-ai-live.plushmole8.chatgpt.site/"),
    ("TenderIQ", "A tender-discovery and bid-management application. I contribute to its development.", "Personal repository · Development contribution", None),
    ("Tutor", "A private Next.js web application. I contribute to its development.", "Personal repository · Development contribution", None),
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
PORTFOLIO_GROUPS = (
    ("Recent development", ("WebGuide AI", "TenderIQ", "Tutor")),
    ("Video systems & investigation", ("E-VMS", "CAAMOO", "ANPR", "Nexus VMS")),
    ("Web products & interfaces", ("Innovathon", "Aurora Ink Genie", "Beauty and wellness website", "Kiru")),
    ("Community bots & automation", ("Age of Telegram · Empire RPG", "Nyther")),
)
# Public descriptions reviewed against project documentation. These describe
# the project, not a claim of sole authorship or connected-service acceptance.
PUBLIC_SUMMARIES = {
    "Evisionindia/.github": "E-Vision India’s company profile, product portfolio and service information.",
    "Evisionindia/EVMS-website": "E-VMS product website, download information and enquiry workflows.",
    "Skill-Aura-Official/Anisha": "Telegram music bot with group-call media playback and queue controls.",
    "Skill-Aura-Official/ANPR": "Vehicle-observation and plate-review prototype with image evidence and alerts.",
    "Skill-Aura-Official/EmpireRPG_Bot": "A text-based empire-building RPG bot for Telegram communities.",
    "Skill-Aura-Official/Innovathon-Public": "SkillAura’s hackathon platform: teams, submissions, judging and leaderboards.",
    "Skill-Aura-Official/Shivratri": "A Python sketch-animation project using a Shiva illustration.",
    "Skill-Aura-Official/Skill-Aura-Official": "My portfolio, approved project contributions and GitHub activity reporting.",
    "Skill-Aura-Official/SkillAura-Pathfinder": "A career-development frontend with onboarding, quests, skill trees and progress views.",
    "Skill-Aura-Official/skillpath-launch": "A career-platform prototype with candidate, recruiter and job-discovery interfaces.",
    "Skill-Aura-Official/TSB-Council": "The Sovereign Brotherhood’s community governance, moderation and policy documents.",
    "Skill-Aura-Official/Hoo-Bank": "My fork of SIYA1104’s banking-style demonstration, with registration, login and dashboard interfaces.",
    "SIYA1104/Hoo-Bank": "Upstream banking-style demonstration by SIYA1104; retained here with its original ownership credit.",
}


def project_summary(repo):
    return PUBLIC_SUMMARIES.get(repo["full_name"], repo.get("description") or
                                "Project details and contributor attribution are available in the repository.")


def card_key(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def card_picture(key, description, url=None):
    picture = (f'<picture><source media="(max-width: 600px)" srcset="assets/cards/{key}-mobile.svg">'
               f'<img src="assets/cards/{key}.svg" alt="{escape(description, quote=True)}" width="100%"></picture>')
    return f'<a href="{escape(url, quote=True)}">{picture}</a>' if url else picture

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
        f"**Explore the portfolio** · {len(CLOSED_SOURCE)} approved project stories · {sum(not r['private'] for r in repos.values())} public repository entries", "",
        "[Public projects](#complete-public-projects) · [Closed-source work](#private--closed-source-projects) · [Technologies](#technologies) · [Activity](#personal-engineering-history)", "",
        "[![Scheduled portfolio refresh](https://github.com/Skill-Aura-Official/Skill-Aura-Official/actions/workflows/refresh-profile.yml/badge.svg?event=schedule)](https://github.com/Skill-Aura-Official/Skill-Aura-Official/actions/workflows/refresh-profile.yml)", "",
        "### Work at a glance", "",
        "- **💻 Web products** · [SkillAura PathFinder AI](https://github.com/Skill-Aura-Official/SkillAura-Pathfinder) and [Innovathon](https://github.com/Skill-Aura-Official/Innovathon-Public)",
        "- **🌱 Recent development work** · [WebGuide AI, TenderIQ and Tutor](#private--closed-source-projects)",
        "- **🤖 Bots and communities** · [Anisha](https://github.com/Skill-Aura-Official/Anisha) and [Empire RPG](https://github.com/Skill-Aura-Official/EmpireRPG_Bot)",
        "- **🧰 Developer tools and automation** · [Portfolio collection and attribution](METHODOLOGY.md)",
        "- **🎥 Video systems and AI** · Contributions to E-Vision’s E-VMS, CAAMOO and ANPR workflows; [roles and team credits below](#private--closed-source-projects)",
        "", "## Personal engineering history", "",
        f"Snapshot {stamp:%d %b %Y, %H:%M UTC}. Coverage **{safe(coverage['status'])}**. Private coverage **{private_status}**.",
        "",
        "These are recorded GitHub events across retrievable history, not a measure of all development work. Project contributions above also include work confirmed by me that is not linked to my GitHub account in commit metadata.", "",
        "**Different scopes:** the repository directory lists projects; ‘Repos with activity’ counts repositories with recorded account-linked events. GitHub’s native calendar below uses its own contribution rules and time window, so its total will differ. [Counting details](METHODOLOGY.md)", "",
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
                  "Development contributions across personal, team and customer work. Repositories remain private where applicable; links lead only to public pages. Ownership and lead credits are shown separately.", ""])
    lines.extend(["**Choose a collection below.** Recent work is open; expand the other collections to browse every card.", ""])
    by_name = {card[0]: card for card in CLOSED_SOURCE}
    for index, (group, names) in enumerate(PORTFOLIO_GROUPS):
        opened = " open" if index == 0 else ""
        lines.extend([f'<details{opened}><summary><strong>{escape(group)}</strong> · {len(names)} projects</summary>', ""])
        for name in names:
            _, summary, attribution, url = by_name[name]
            lines.extend([f'<a name="{card_key(name)}"></a>', "",
                          card_picture("closed-" + card_key(name), name + ". " + attribution + ". " + summary, url), ""])
        lines.extend(["</details>", ""])
    lines.extend(["", "## Complete public projects", "",
        "Every public repository in the current inventory is linked below, including forks and collaborations. Repository ownership does not imply sole authorship. Detailed commit counts stay in the [activity index](PUBLIC_PROJECTS.md).", ""])

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
        lines.extend([f'<details><summary><strong>{escape(group)}</strong> · {len(groups[group])} repositories</summary>', ""])
        for repo in sorted(groups[group], key=lambda r: r["full_name"].casefold()):
            name = repo["full_name"]
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name):
                raise ValueError("Unsafe public repository name")
            lines.extend([card_picture("public-" + str(repo["id"]), name + ". " + project_summary(repo), "https://github.com/" + name), ""])
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
                safe(project_summary(repo)), metadata, "",
                f"{safe(repo['relationship'])}. {'Archived. ' if repo['archived'] else ''}{period}.",
                "", " · ".join(f"{'Account-linked commits' if kind == 'commit' else label} **{counts[kind] if repo['scanned'] else ('≥' + str(counts[kind]) if counts[kind] else 'Unknown')}**" for kind, label in METRICS), ""])
        lines.extend(["</details>", ""])
    lines.extend(["[Open the full repository metrics and activity index](PUBLIC_PROJECTS.md)", "",
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
    # Put the work before the metrics; retain every section and generated record.
    content = "\n".join(lines)
    intro, rest = content.split("## Personal engineering history", 1)
    history, portfolio = rest.split("## Private / Closed-source Projects", 1)
    content = intro + "## Private / Closed-source Projects" + portfolio + "\n\n## Personal engineering history" + history
    return content.rstrip() + "\n", "\n".join(directory)


def svg_start(width, height, title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img"><title>{escape(title)}</title>',
            '<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#07111f"/><stop offset="1" stop-color="#17172e"/></linearGradient></defs>',
            f'<rect width="{width}" height="{height}" rx="18" fill="url(#bg)"/>']


def svg_text(x,y,text,size=16,color="#c6d4e5",weight=400):
    return f'<text x="{x}" y="{y}" font-family="Arial,sans-serif" font-size="{size}" fill="{color}" font-weight="{weight}">{escape(str(text))}</text>'


def graphic(data, mobile=False):
    repos,totals,years,worked=summarize(data)
    private_available = any(r["private"] and r["scanned"] for r in repos.values())
    width=360 if mobile else 840
    columns=2 if mobile else 4
    card_width=(width-36-(columns-1)*12)/columns
    metrics=[("Repos with activity",len(worked["public"]),len(worked["private"]),None)]
    metrics.extend((label,totals["public",kind],totals["private",kind],kind) for kind,label in METRICS if kind not in ("issue_comment","review_comment"))
    metrics.insert(5,("Comments",sum(totals["public",k] for k in ("issue_comment","review_comment")),
                     sum(totals["private",k] for k in ("issue_comment","review_comment")),"issue_comment"))
    rows=(len(metrics)+columns-1)//columns
    parts=svg_start(width,58+rows*112,"All-time attributable personal activity")
    parts.append(svg_text(18,29,"RECORDED ACTIVITY · ALL TIME",14,"#79d5fa",700))
    for i,(label,pub,private,kind) in enumerate(metrics):
        x=18+(i%columns)*(card_width+12)
        y=48+(i//columns)*112
        public_text=figure(repos,"public",kind,pub) if kind else str(pub)
        private_text=figure(repos,"private",kind,private) if kind else str(private)
        if label == "Comments":
            # Both comment sources must be covered before showing an exact sum.
            for scope, value in (("public", pub), ("private", private)):
                figures = [figure(repos, scope, source, value) for source in ("issue_comment", "review_comment")]
                combined = str(value) if all(v == str(value) for v in figures) else ("≥" + str(value) if value else "Unknown")
                if scope == "public": public_text = combined
                else: private_text = combined
        if not private_available:
            private_text = "Unknown"
        parts.extend([f'<rect x="{x}" y="{y}" width="{card_width}" height="100" rx="10" fill="#101f32" stroke="#2b3c55"/>',
                      svg_text(x+12,y+23,label,13 if mobile else 16,"#bfcddd",600),
                      svg_text(x+12,y+54,public_text,25,"#73d3fa",700),
                      svg_text(x+card_width/2+8,y+54,private_text,25,"#b6a2fa",700),
                      svg_text(x+12,y+80,"Public",14),
                      svg_text(x+card_width/2+8,y+80,"Private",14)])
    return ("".join(parts)+"</svg>").encode()


def timeline(data,mobile=False):
    repos,_,years,_=summarize(data)
    width=360 if mobile else 840
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
        label_step = max(1, (len(ordered) + 9) // 10)
        if i in (0,len(ordered)-1) or (not mobile and i % label_step == 0):
            parts.append(svg_text(x,year_height+176,month[2:],11))
    parts.append(svg_text(18,height-15,"Monthly values in the activity index.",12))
    return ("".join(parts)+"</svg>").encode()


def artwork(data):
    result = {"assets/hero.svg":hero(),"assets/hero-mobile.svg":hero(True),
            "assets/activity.svg":graphic(data),"assets/activity-mobile.svg":graphic(data,True),
            "assets/timeline.svg":timeline(data),"assets/timeline-mobile.svg":timeline(data,True),
            "assets/projects.svg":project_graphic(data),"assets/projects-mobile.svg":project_graphic(data,True)}
    cards = [("closed-" + card_key(name), name, attribution, summary)
             for name, summary, attribution, _ in CLOSED_SOURCE]
    cards.extend(("public-" + str(repo["id"]), repo["full_name"].split("/")[-1],
                  repo["owner"] + " · " + repo["relationship"], project_summary(repo))
                 for repo in data["repositories"] if not repo["private"])
    for key, title, credit, description in cards:
        for mobile in (False, True):
            suffix = "-mobile" if mobile else ""
            result[f"assets/cards/{key}{suffix}.svg"] = portfolio_card(title, credit, description, mobile)
    return result


def hero(mobile=False):
    width, height = (360, 260) if mobile else (840, 246)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
             '<title>Jatin Dalal — software, AI interfaces and automation. SkillAura, community work and E-Vision contributions.</title>',
             '<style>.trace{stroke-dasharray:22 380;animation:travel 14s linear infinite}@keyframes travel{to{stroke-dashoffset:-804}}@media(prefers-reduced-motion:reduce){.trace{animation:none;stroke-dasharray:none}}</style>',
             f'<rect width="{width}" height="{height}" rx="20" fill="#09171c"/>',
             f'<path d="M24 {height-25} H{width-24}" stroke="#28434a" stroke-width="1"/>',
             f'<path class="trace" d="M24 {height-25} H{width-24}" stroke="#7ee1cb" stroke-width="3" fill="none"/>']
    x = 24 if mobile else 32
    parts.extend([svg_text(x, 40, "SKILLAURA / PERSONAL PORTFOLIO", 12, "#7ee1cb", 700),
                  svg_text(x, 93, "Jatin Dalal", 39 if mobile else 49, "#f2f3ec", 700),
                  svg_text(x, 127, "Software · AI interfaces", 18 if mobile else 21, "#e0e8e4"),
                  svg_text(x, 154, "& automation", 18 if mobile else 21, "#e0e8e4"),
                  svg_text(x, 196 if mobile else 200, "Build. Connect. Keep improving.", 15, "#b4c8c3")])
    if not mobile:
        parts.extend(['<rect x="555" y="44" width="250" height="134" rx="12" fill="#11272c" stroke="#365058"/>',
                      svg_text(576, 74, "IDEA  →  INTERFACE", 15, "#7ee1cb", 700),
                      svg_text(576, 109, "API   →  WORKFLOW", 15, "#d9e8e0", 700),
                      svg_text(576, 144, "TEST  →  ITERATE", 15, "#e6c28c", 700)])
    return ("".join(parts) + "</svg>").encode()


def portfolio_card(title, credit, description, mobile=False):
    width = 360 if mobile else 840
    # Separate variants keep type readable instead of scaling a desktop grid down.
    title_lines = textwrap.wrap(title, width=26 if mobile else 62)
    credit_lines = textwrap.wrap(credit, width=39 if mobile else 94)
    body_lines = textwrap.wrap(description, width=36 if mobile else 83)
    height = 44 + len(title_lines) * 28 + len(credit_lines) * 21 + len(body_lines) * 25
    parts = svg_start(width, height, title + ". " + credit + ". " + description)
    parts.append(f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="17" fill="none" stroke="#334865"/>')
    parts.append(f'<rect x="0" y="20" width="4" height="{height-40}" rx="2" fill="#79d5fa"/>')
    y = 34
    for line in title_lines:
        parts.append(svg_text(22, y, line, 22, "#f4f7ff", 700)); y += 28
    for line in credit_lines:
        parts.append(svg_text(22, y, line, 14, "#91ddfa")); y += 21
    y += 10
    for line in body_lines:
        parts.append(svg_text(22, y, line, 16 if mobile else 18, "#e0e8f2")); y += 25
    return ("".join(parts) + "</svg>").encode()


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
        desc=project_summary(repo)
        desc_lines=textwrap.wrap(desc,width=41 if mobile else 66)[:2]
        count=len({r.get("sha") or r["id"] for r in data["records"] if str(r["repo_id"])==str(repo["id"]) and r["type"]=="commit"})
        parts.append(f'<rect x="{x}" y="{y}" width="{card_width}" height="138" rx="12" fill="#101f32" stroke="#2b3c55"/>')
        parts.append(svg_text(x+14,y+26,name[:38],16,"#f4f7ff",700))
        parts.append(svg_text(x+14,y+47,repo["owner"],12,"#79d5fa"))
        for n,line in enumerate(desc_lines):
            parts.append(svg_text(x+14,y+71+n*17,line,12))
        details=[repo.get("language") or "",f"{count} account-linked commits" if repo["scanned"] else "Activity partially available"]
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
