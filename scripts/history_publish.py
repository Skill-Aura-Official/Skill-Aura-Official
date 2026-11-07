"""Publish detailed history privately and sanitized, semantic profile changes publicly."""
import argparse
import base64
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from render_history import render, graphic

ACCOUNT = "Skill-Aura-Official"
PROFILE = ACCOUNT + "/" + ACCOUNT
STATE_MARKER = "Private personal work inventory and history checkpoints"
IDENTITY_COMMIT = "17a7b2d0da3b0a6f1a64c124170cbb940ef7d042"


class Publisher:
    def __init__(self, token):
        self.token = token
        user = self.api("user")
        if user["login"] != ACCOUNT:
            raise ValueError("Unexpected publication account")
        linked = self.api("repos/" + PROFILE + "/commits/" + IDENTITY_COMMIT)
        if linked["author"]["login"] != ACCOUNT or linked["committer"]["login"] != ACCOUNT:
            raise ValueError("Publication identity linkage failed")
        self.identity = {k: linked["commit"]["author"][k] for k in ("name", "email")}
        self.state_repo = None
        page = 1
        while True:
            repos = self.api(f"user/repos?per_page=100&page={page}")
            for repo in repos:
                if repo["private"] and repo["owner"]["login"] == ACCOUNT and repo["description"] == STATE_MARKER:
                    if self.state_repo:
                        raise ValueError("Ambiguous private history destination")
                    self.state_repo = repo["full_name"]
            if len(repos) < 100:
                break
            page += 1
        if not self.state_repo:
            raise ValueError("Private history destination unavailable to publication credential")

    def api(self, route, body=None, method=None):
        request = Request("https://api.github.com/" + route,
            data=None if body is None else json.dumps(body).encode(),
            method=method, headers={
                "Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
                "User-Agent": "SkillAura-history-publication", "Content-Type": "application/json",
            })
        try:
            with urlopen(request, timeout=60) as response:
                return json.load(response)
        except HTTPError as exc:
            # Never expose response payloads or a private destination in logs.
            raise RuntimeError(f"History publication HTTP {exc.code}") from None

    def head(self, repo):
        info = self.api("repos/" + repo)
        if repo == self.state_repo and not info["private"]:
            raise ValueError("History destination must be private")
        default = info["default_branch"]
        if default != "main":
            raise ValueError("Unexpected destination default branch")
        try:
            head = self.api("repos/" + repo + "/git/ref/heads/main")["object"]["sha"]
        except RuntimeError as exc:
            if repo == self.state_repo and ("409" in str(exc) or "404" in str(exc)):
                return None, None
            raise
        tree = self.api("repos/" + repo + "/git/commits/" + head)["tree"]["sha"]
        return head, tree

    def read(self, repo, filename):
        try:
            result = self.api("repos/" + repo + "/contents/" + filename)
        except RuntimeError as exc:
            if "404" in str(exc):
                return None
            raise
        if result.get("encoding") == "base64" and result.get("content"):
            return base64.b64decode(result["content"])
        blob = self.api("repos/" + repo + "/git/blobs/" + result["sha"])
        return base64.b64decode(blob["content"])

    def commit_files(self, repo, files, message):
        head, previous_tree = self.head(repo)
        if head is None:
            if repo != self.state_repo:
                raise ValueError("Refusing to initialize a public repository")
            seed = self.api("repos/" + repo + "/contents/README.md", {
                "message": "Initialize private history storage\n\nAutomation: profile-history",
                "content": base64.b64encode(b"# Private work history\n\nDetailed inventory, CSV exports and collector checkpoints. Repository access controls protect this data.\n").decode(),
                "author": self.identity, "committer": self.identity, "branch": "main",
            }, "PUT")
            head = seed["commit"]["sha"]
            previous_tree = seed["commit"]["tree"]["sha"]
        entries = []
        for name, data in files.items():
            blob = self.api("repos/" + repo + "/git/blobs",
                            {"content": base64.b64encode(data).decode(), "encoding": "base64"})
            entries.append({"path": name, "type": "blob", "mode": "100644", "sha": blob["sha"]})
        body = {"tree": entries}
        if previous_tree:
            body["base_tree"] = previous_tree
        tree = self.api("repos/" + repo + "/git/trees", body)["sha"]
        commit = self.api("repos/" + repo + "/git/commits", {
            "message": message, "tree": tree, "parents": [head] if head else [],
            "author": self.identity, "committer": self.identity,
        })["sha"]
        if head:
            self.api("repos/" + repo + "/git/refs/heads/main",
                     {"sha": commit, "force": False}, "PATCH")
        else:
            self.api("repos/" + repo + "/git/refs", {"ref": "refs/heads/main", "sha": commit})
        verified = self.api("repos/" + repo + "/commits/" + commit)
        if any((verified.get(key) or {}).get("login") != ACCOUNT for key in ("author", "committer")):
            raise ValueError("Published commit identity could not be verified")
        return commit


def csv_bytes(data):
    stream = io.StringIO(newline="")
    fields = ("repo_id", "type", "id", "sha", "date", "branches", "role", "html_url", "title")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for record in data["records"]:
        row = dict(record)
        row["branches"] = json.dumps(row.get("branches", []), ensure_ascii=False)
        # Excel must interpret untrusted titles as text.
        for key, value in row.items():
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                row[key] = "'" + value
        writer.writerow(row)
    return stream.getvalue().encode("utf-8-sig")


def semantic_public(data):
    # Hash only what a visitor actually sees. Raw metadata such as branch heads
    # and individual source scan times must never create another profile commit.
    stable = dict(data, snapshot_at="2000-01-01T00:00:00Z")
    readme, directory = render(stable)
    return {"readme": readme, "directory": directory, "graphic": graphic(stable).decode()}


def semantic_private(data):
    """Compare records, repository tips and access state, omitting run timestamps."""
    state = copy.deepcopy(data)
    for key in ("snapshot_at", "last_attempt_at", "last_success_at", "last_full_at"):
        state.pop(key, None)
    state["coverage"].pop("mode", None)
    for source in state["coverage"].get("sources", []):
        source.pop("from", None)
        source.pop("to", None)
    for repo in state["repositories"]:
        repo.pop("last_attempt_at", None)
        repo.pop("last_success_at", None)
        if repo["full_name"].casefold() == PROFILE.casefold():
            # The generated public snapshot itself advances this tip. Changes
            # to attributable profile records still trigger a checkpoint.
            repo.pop("branch_heads", None)
        for source in repo.get("source_coverage", {}).values():
            for key in ("from", "to", "last_attempt_at", "last_success_at"):
                source.pop(key, None)
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("pull", "publish"))
    parser.add_argument("inventory", type=Path)
    args = parser.parse_args()
    publisher = Publisher(os.environ["PROFILE_PUBLISH_TOKEN"])
    if args.action == "pull":
        payload = publisher.read(publisher.state_repo, "inventory.json")
        if payload:
            args.inventory.parent.mkdir(parents=True, exist_ok=True)
            args.inventory.write_bytes(payload)
        return
    data = json.loads(args.inventory.read_text(encoding="utf-8-sig"))
    if data["account"] != ACCOUNT:
        raise ValueError("Unexpected inventory account")
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True).encode()
    previous_private = publisher.read(publisher.state_repo, "inventory.json")
    if previous_private is None or semantic_private(json.loads(previous_private)) != semantic_private(data):
        publisher.commit_files(publisher.state_repo,
            {"inventory.json": payload, "exports/inventory.json": payload, "exports/records.csv": csv_bytes(data)},
            "Update private history checkpoint\n\nAutomation: profile-history")
    else:
        print("Private records and access unchanged; no checkpoint commit created.")
    semantic = json.dumps(semantic_public(data), sort_keys=True).encode()
    signature = hashlib.sha256(semantic).hexdigest().encode()
    previous = publisher.read(PROFILE, "assets/history-signature.txt")
    if previous == signature:
        print("Public history data unchanged; no profile commit created.")
        return
    readme, directory = render(data)
    commit = publisher.commit_files(PROFILE, {"README.md": readme.encode(), "PUBLIC_PROJECTS.md": directory.encode(), "assets/activity.svg": graphic(data),
        "assets/history-signature.txt": signature},
        "Automated profile inventory snapshot\n\nAutomation: profile-history")
    print("Published sanitized all-time profile snapshot " + commit)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(str(exc) if isinstance(exc, (ValueError, RuntimeError)) else "History publication failed")
