"""Refresh the public portfolio only after every required API read succeeds."""
import datetime as dt
import json
import os
import urllib.request
import urllib.error
from collections import Counter
from pathlib import Path

OWNER = "Skill-Aura-Official"
ROOT = Path(__file__).resolve().parents[1]

def get(path):
    headers = {"User-Agent": "SkillAura-public-profile"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request("https://api.github.com/" + path, headers=headers), timeout=25) as response:
        return json.load(response)

def collect():
    user = get("users/" + OWNER)
    repos = []
    page = 1
    while True:
        batch = get(f"users/{OWNER}/repos?type=owner&per_page=100&page={page}")
        if not isinstance(batch,list):
            raise ValueError("Unexpected repository listing")
        for repo in batch:
            if repo["private"] or repo["visibility"] != "public" or repo["owner"]["login"] != OWNER:
                raise ValueError("Unexpected repository scope")
        repos.extend(batch)
        if len(batch)<100:
            break
        page += 1
    if len({repo["id"] for repo in repos}) != user["public_repos"] or len(repos)!=user["public_repos"]:
        raise ValueError("Incomplete public repository inventory")
    languages = Counter()
    activity = []
    for repo in repos:
        if repo["fork"] or repo["name"]==OWNER:
            continue
        path = "repos/" + repo["full_name"]
        langs = get(path + "/languages")
        if not isinstance(langs,dict) or any(type(v)!=int or v<0 for v in langs.values()):
            raise ValueError("Invalid language data")
        languages.update(langs)
        try:
            commits = get(path + "/commits?per_page=1")
        except urllib.error.HTTPError as exc:
            if exc.code==409 and repo["size"]==0:
                continue
            raise
        c=commits[0]
        activity.append((c["commit"]["committer"]["date"],repo["name"],c["sha"]))
    return repos,languages,sorted(activity,reverse=True)

def render():
    repos,languages,activity=collect()
    names={r["name"] for r in repos}
    lines=["# SkillAura","", "I build operator tools and web applications. My current ANPR work focuses on what happens after a plate is read: reviewing the vehicle record, checking a watchlist match, and retrieving the original image.","","## Selected work",""]
    for name,description in [("ANPR","Vehicle recognition evaluation. A local operator workflow has demonstrated image-based plate reading, watchlist alerts and evidence retrieval."),("EmpireRPG_Bot","Age of Telegram, an empire RPG bot.")]:
        if name in names:
            lines.append(f"- **[{name}](https://github.com/{OWNER}/{name})** — {description}")
    lines+=["","## Public development snapshot","",f"{len(repos)} public repositories owned by this account, including forks ({sum(r['fork'] for r in repos)}). Source and activity measurements below exclude forks and the profile repository.","","### Languages by source bytes",""]
    total=sum(languages.values())
    for name,count in languages.most_common(6):
        lines.append(f"- {name}: {count:,} bytes ({count/total:.1%})")
    lines+=["","### Recent repository commits","","Latest default-branch commit in each of the five most recently committed public projects. These include work by all authors.",""]
    for date,name,sha in activity[:5]:
        lines.append(f"- {date[:10]} · [{name} · `{sha[:7]}`](https://github.com/{OWNER}/{name}/commit/{sha})")
    stamp=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    lines+=["","## Connect","",f"[GitHub profile and contribution graph](https://github.com/{OWNER}) · [Public repositories](https://github.com/{OWNER}?tab=repositories)","","Snapshot from the GitHub REST API. Scheduled every six hours. Last successful data refresh: "+stamp+"."]
    return "\n".join(lines)+"\n"

if __name__=="__main__":
    content=render()
    output=ROOT/"README.next"
    output.write_text(content,encoding="utf8")
    output.replace(ROOT/"README.md")
