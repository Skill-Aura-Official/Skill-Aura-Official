"""Attribute GitHub activity. Keep repository and event identifiers in memory only."""
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OWNER = "Skill-Aura-Official"
PROFILE = f"{OWNER}/{OWNER}".lower()
FIELDS = ("commits", "pull_requests", "reviews", "issues")
SCOPES = ("public", "private")
DAY = dt.timedelta(days=1)
UTC = dt.timezone.utc
DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


class Incomplete(Exception):
    """An incomplete API result may never replace a successful refresh."""


class API:
    def __init__(self, token):
        self.token = token

    def get(self, path, params=None):
        url = "https://api.github.com/" + path
        if params:
            url += "?" + urlencode(params)
        headers = {"User-Agent": "SkillAura-activity", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        for attempt in range(3):
            try:
                with urlopen(Request(url, headers=headers), timeout=30) as response:
                    return json.load(response)
            except HTTPError as exc:
                if exc.code == 409 and path.endswith("/branches"):
                    return []
                delay = int(exc.headers.get("Retry-After", 0))
                if exc.headers.get("X-RateLimit-Remaining") == "0":
                    delay = max(delay, int(exc.headers.get("X-RateLimit-Reset", 0)) - int(time.time()) + 1)
                retry = exc.code in (429, 500, 502, 503, 504) or (exc.code == 403 and delay > 0)
                if not retry or delay > 60 or attempt == 2:
                    raise Incomplete(f"API HTTP {exc.code}; snapshot retained") from None
                time.sleep(max(delay, 2 ** attempt))
            except (URLError, TimeoutError):
                if attempt == 2:
                    raise Incomplete("API connection failed; snapshot retained") from None
                time.sleep(2 ** attempt)

    def pages(self, path, params=None):
        page = 1
        while True:
            result = self.get(path, {**(params or {}), "page": page, "per_page": 100})
            if not isinstance(result, list):
                raise Incomplete("Unexpected API response")
            yield from result
            if len(result) < 100:
                return
            page += 1


def inventory(clients, personal):
    repos = {}
    for api in clients:
        if personal:
            if api.get("user")["login"].casefold() != OWNER.casefold():
                raise Incomplete("Unexpected collector account")
            sources = [("user/repos", {"visibility": "all", "affiliation": "owner,collaborator,organization_member"})]
        else:
            sources = [(f"users/{owner}/repos", {"type": "owner"}) for owner in (OWNER, "Evisionindia")]
        for path, params in sources:
            for repo in api.pages(path, params):
                if not personal and repo["private"]:
                    raise Incomplete("Unexpected fallback visibility")
                repos[repo["id"]] = (repo, api)
    return repos


def is_person(account):
    return (account or {}).get("login", "").casefold() == OWNER.casefold() and account.get("type") == "User"


def search(api, query, start, end, qualifier):
    """Split saturated date ranges. Incomplete indexes must never become zeros."""
    page = 1
    expected = None
    seen = set()
    while True:
        q = f"{query} {qualifier}:{start.isoformat()}..{end.isoformat()}"
        result = api.get("search/issues", {"q": q, "page": page, "per_page": 100})
        if result.get("incomplete_results") is not False:
            raise Incomplete("Search timed out")
        total = result["total_count"]
        if total > 1000:
            if start == end:
                raise Incomplete("Search exceeds the per-day API limit")
            midpoint = start + (end - start) // 2
            yield from search(api, query, start, midpoint, qualifier)
            yield from search(api, query, midpoint + DAY, end, qualifier)
            return
        if expected is None:
            expected = total
        if total != expected:
            raise Incomplete("Search changed during pagination")
        for item in result["items"]:
            seen.add(item["id"])
            yield item
        if page * 100 >= total:
            if len(seen) != expected:
                raise Incomplete("Search pagination incomplete")
            return
        page += 1


def collect_events(repos, clients, start, end, cutoff, examples=None):
    events = {}
    names = {r["full_name"].casefold(): (r, api) for r, api in repos.values()}
    def add(kind, ident, stamp, repo):
        date = stamp[:10]
        if not start.isoformat() <= date <= end.isoformat() or stamp > cutoff:
            return
        key = kind, ident
        scope = "private" if repo["private"] else "public"
        if key not in events or scope == "public":
            events[key] = (date, scope, kind)
        if examples is not None and kind == "commits":
            examples.setdefault(scope, {"repository": repo["full_name"], "sha": ident, "account": OWNER})

    for repo, api in repos.values():
        if not repo["pushed_at"] or repo["pushed_at"][:10] < start.isoformat():
            continue
        path = f"repos/{repo['full_name']}"
        tips = {b["commit"]["sha"] for b in api.pages(path + "/branches")}
        for tip in tips:
            params = {"sha": tip, "author": OWNER, "since": str(start) + "T00:00:00Z", "until": cutoff}
            for row in api.pages(path + "/commits", params):
                if not is_person(row["author"]) or len(row["parents"]) > 1:
                    continue
                if (row.get("committer") or {}).get("type") == "Bot":
                    continue
                if repo["full_name"].casefold() == PROFILE and row["commit"]["message"].splitlines()[0] == "Refresh public repository snapshot":
                    continue
                add("commits", row["sha"], row["commit"]["committer"]["date"], repo)

    for api in clients:
        for query, qualifier, metric in [
            (f"author:{OWNER} is:pr", "created", "pull_requests"),
            (f"author:{OWNER} is:issue", "created", "issues"),
            (f"reviewed-by:{OWNER} is:pr", "updated", "reviews")
        ]:
            for item in search(api, query, start, end, qualifier):
                name = item["repository_url"].removeprefix("https://api.github.com/repos/").casefold()
                if name not in names:
                    continue
                repo, repo_api = names[name]
                if metric != "reviews":
                    if is_person(item["user"]):
                        add(metric, item["id"], item["created_at"], repo)
                    continue
                path = f"repos/{repo['full_name']}/pulls/{item['number']}/reviews"
                for review in repo_api.pages(path):
                    if is_person(review["user"]) and review.get("submitted_at"):
                        add(metric, review["id"], review["submitted_at"], repo)
    return events.values()


def empty_day():
    return {scope: {metric: 0 for metric in FIELDS} for scope in SCOPES}


def validate(state):
    if set(state) != {"version","as_of","reconciled","coverage","days"} or state["version"] != 1:
        raise Incomplete("Unexpected public snapshot schema")
    if state["coverage"] not in ("VISIBLE_PRIVATE_SUBSET", "PRIVATE_UNKNOWN"):
        raise Incomplete("Unexpected coverage label")
    for field in ("as_of","reconciled"):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", state[field]):
            raise Incomplete("Invalid public timestamp")
        dt.datetime.fromisoformat(state[field].replace("Z","+00:00"))
    end = dt.date.fromisoformat(state["as_of"][:10])
    if set(state["days"]) != {(end-i*DAY).isoformat() for i in range(30)}:
        raise Incomplete("Incomplete date coverage")
    for date, rows in state["days"].items():
        if not DATE.fullmatch(date) or set(rows) != set(SCOPES):
            raise Incomplete("Unexpected public data")
        for scope in SCOPES:
            if set(rows[scope]) != set(FIELDS):
                raise Incomplete("Unexpected public counters")
            for n in rows[scope].values():
                if scope == "private" and state["coverage"] == "PRIVATE_UNKNOWN":
                    if n is not None:
                        raise Incomplete("Unknown coverage must have null counters")
                elif type(n) is not int or n < 0:
                    raise Incomplete("Invalid aggregate counter")
    return state


def refresh(clients, personal, previous, now, examples=None, force=False):
    if previous:
        validate(previous)
    repos = inventory(clients, personal)
    coverage = "VISIBLE_PRIVATE_SUBSET" if any(r["private"] for r, _ in repos.values()) else "PRIVATE_UNKNOWN"
    if previous and previous["coverage"] == "VISIBLE_PRIVATE_SUBSET" and coverage == "PRIVATE_UNKNOWN":
        raise Incomplete("Private coverage lost; previous snapshot retained")
    end = now.date()
    cutoff = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    first = end - 29*DAY
    # Refresh the previous two UTC dates plus today. Full reconciliation every seven days or on demand.
    full = (force or not previous or previous["coverage"] != coverage or
            end - dt.date.fromisoformat(previous["reconciled"][:10]) >= 7*DAY)
    start = first if full else max(first,min(end,dt.date.fromisoformat(previous["as_of"][:10])) - 2*DAY)
    days = {}
    for i in range(30):
        date = (first + i*DAY).isoformat()
        days[date] = previous["days"][date] if date < str(start) else empty_day()
        if coverage == "PRIVATE_UNKNOWN":
            days[date]["private"] = dict.fromkeys(FIELDS)
    for date, scope, kind in collect_events(repos, clients, start, end, cutoff, examples):
        days[date][scope][kind] += 1
    return validate({"version":1,"as_of":cutoff,"reconciled":cutoff if full else previous["reconciled"],
                     "coverage":coverage,"days":days})


def summary(state):
    validate(state)
    stamp = dt.datetime.fromisoformat(state["as_of"].replace("Z","+00:00"))
    stale = (stamp + dt.timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M UTC")
    lines = ["## Personal GitHub activity · last 30 UTC dates",
             f"Last successful collection {state['as_of']}. Treat as stale after {stale}.",
             "","| Personal activity | Public repositories | Private repositories |",
             "|---|---:|---:|"]
    for key,label in zip(FIELDS, ["Commits","Pull requests opened","Reviews submitted","Issues opened"]):
        counts = []
        for scope in SCOPES:
            if scope == "private" and state["coverage"] == "PRIVATE_UNKNOWN":
                counts.append("UNKNOWN")
            else:
                counts.append(str(sum(day[scope][key] for day in state["days"].values())))
        lines.append(f"| {label} | {' | '.join(counts)} |")
    lines.extend(["", "Coverage is PARTIAL across the account. Counts cover repositories visible to the collector. "
                  "Unseen repositories have unknown activity."])
    return "\n".join(lines) + "\n"


def main():
    tokens = [os.environ.get(k) for k in ("PROFILE_ACTIVITY_READ_TOKEN","PROFILE_ACTIVITY_ORG_READ_TOKEN")]
    clients = [API(t) for t in tokens if t]
    personal = bool(clients)
    if not clients:
        clients = [API(os.environ.get("GITHUB_TOKEN"))]
    previous_file = Path("previous/aggregate.json")
    previous = json.loads(previous_file.read_text()) if previous_file.exists() else None
    state = refresh(clients, personal, previous, dt.datetime.now(UTC),
                    force=os.getenv("FULL_RECONCILE") == "true")
    output = Path("output")
    output.mkdir(exist_ok=True)
    (output/"aggregate.json").write_text(json.dumps(state,sort_keys=True),encoding="utf8")
    report = summary(state)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf8") as f:
            f.write(report)
    else:
        print(report)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # No raw responses, private paths, payloads or exception chains in public Actions logs.
        print(str(exc) if isinstance(exc, Incomplete) else "Refresh incomplete; prior successful snapshot retained.",file=sys.stderr)
        sys.exit(1)
