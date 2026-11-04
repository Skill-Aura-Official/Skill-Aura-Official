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
    import subprocess
    import tempfile
    projects=[]
    for repo in repos:
        if repo["name"]==OWNER:
            continue
        original=not repo["fork"]
        projects.append(dict(owner=OWNER,repository=repo["name"],displayName=repo["name"],
            category="skillAura" if original else "fork",visibility="public",tags=[],
            description=("Image recognition, vehicle review and watchlist alerts." if repo["name"]=="ANPR" else repo["description"] or "Public project by SkillAura."),
            includeInPortfolio=original,includeInStats=original,includeInActivity=original,includeInLanguages=original))
    projects.append(dict(owner="Evisionindia",repository="EVMS-website",displayName="E-VMS",category="external",
        visibility="public",tags=[],includeInStats=True,includeInActivity=True,includeInLanguages=False))
    manifest=dict(projects=projects,publicCount=len(repos),technologyFootprint=list(dict(languages.most_common(6))),
        profile={"summary":"A portfolio of software products, web platforms, automation projects, and engineering work."},
        commits=" · ".join(f"[{name} `{sha[:7]}`](https://github.com/{OWNER}/{name}/commit/{sha})" for _,name,sha in activity[:5]))
    with tempfile.TemporaryDirectory() as temp:
        data=Path(temp)/"public.json"
        data.write_text(json.dumps(manifest),encoding="utf8")
        subprocess.run(["node","scripts/generate-profile.mjs",str(data)],cwd=ROOT,check=True)

if __name__=="__main__":
    render()
