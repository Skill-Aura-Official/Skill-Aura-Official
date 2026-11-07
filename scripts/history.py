"""Build an owner-only inventory from GitHub. Only a renderer may derive public output."""
import argparse
from collections import defaultdict
from copy import deepcopy
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import technologies

OWNER = "Skill-Aura-Official"
UTC = dt.timezone.utc
DAY = dt.timedelta(days=1)
PAGE = "pageInfo {hasNextPage endCursor}"
PROFILE = f"{OWNER}/{OWNER}".lower()
STATE_MARKER = "Private personal work inventory and history checkpoints"
AUTOMATION_PATHS = {"README.md","PUBLIC_PROJECTS.md","assets/activity.svg","assets/activity-mobile.svg",
                    "assets/timeline.svg","assets/timeline-mobile.svg","assets/projects.svg","assets/projects-mobile.svg",
                    "assets/history-signature.txt"}
TYPES = {"commit","pr","issue","review","issue_comment","review_comment","release","discussion"}
COLLECTION_REVISION = 2


class Failure(Exception):
    """Safe for public Actions output: never include API payloads, routes or identifiers."""
    def __init__(self, status, source):
        self.status, self.source = status, source
        super().__init__(f"{source} incomplete ({status})")


def unexpected_failure_category(error):
    """Emit only allowlisted labels. Exception messages can contain private payloads."""
    for kind, label in (
        (json.JSONDecodeError, "invalid-json"),
        (TimeoutError, "timeout"),
        (OSError, "file-or-network-io"),
        (KeyError, "missing-data-field"),
        (TypeError, "unexpected-data-type"),
        (ValueError, "invalid-data-value"),
    ):
        if isinstance(error, kind):
            return label
    return "unexpected"


def timestamp(value):
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(value):
    return dt.datetime.fromisoformat(value.replace("Z","+00:00"))


def operation(path):
    # Use only constant category names in public logs, including for malformed routes.
    routes = [
        (r"user","account identity"),(r"user/repos","affiliated inventory"),(r"user/orgs","membership inventory"),
        (r"users/[^/]+/repos","owned public inventory"),(r"orgs/[^/]+/repos","organization inventory"),
        (r"users/[^/]+/events/public","recent public-event discovery"),(r"search/issues","typed issue/PR discovery"),
        (r"search/commits","global commit discovery"),(r"graphql","GraphQL history query"),
        (r"repositories/\d+|repos/[^/]+/[^/]+","repository identity"),
        (r"repos/[^/]+/[^/]+/branches","branch inventory"),(r"repos/[^/]+/[^/]+/commits/[^/]+","commit attribution"),
        (r"repos/[^/]+/[^/]+/issues","issue inventory"),(r"repos/[^/]+/[^/]+/pulls","pull request inventory"),
        (r"repos/[^/]+/[^/]+/pulls/\d+/reviews","review inventory"),(r"repos/[^/]+/[^/]+/issues/comments","issue comments"),
        (r"repos/[^/]+/[^/]+/pulls/comments","review comments"),(r"repos/[^/]+/[^/]+/releases","release inventory"),
        (r"repos/[^/]+/[^/]+/(?:languages|git/(?:trees|blobs)/[^/]+)","technology source inventory"),
    ]
    return next((label for regex,label in routes if re.fullmatch(regex,path)),"unclassified API operation")


def typed_searches():
    # A scoped GitHub user credential can receive HTTP 422 for mixed issues and PRs.
    for actor,qualifier in (("author","created"),("commenter","updated")):
        for kind in ("issue","pr"):
            yield f"{actor}:{OWNER} is:{kind}",qualifier
    yield f"reviewed-by:{OWNER} is:pr","updated"


class GitHub:
    def __init__(self, token):
        self.token = token

    def request(self, path, params=None, data=None):
        route = "https://api.github.com/" + path
        if params:
            route += "?" + urlencode(params)
        req = Request(route, data=json.dumps(data).encode() if data else None, headers={
            "Authorization":"Bearer "+self.token, "User-Agent":"SkillAura-private-history",
            "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json"})
        for attempt in range(4):
            try:
                with urlopen(req,timeout=55) as response:
                    return json.load(response)
            except HTTPError as exc:
                delay = int(exc.headers.get("Retry-After") or 0)
                if exc.headers.get("X-RateLimit-Remaining") == "0":
                    delay=max(delay,int(exc.headers.get("X-RateLimit-Reset") or 0)-int(time.time())+1)
                retry=exc.code in (429,500,502,503,504) or (exc.code==403 and delay>0)
                if not retry or attempt==3 or delay>150:
                    raise Failure(exc.code, operation(path)) from None
                time.sleep(max(delay,2**attempt))
            except (URLError,TimeoutError,ConnectionError):
                if attempt==3:
                    raise Failure("network", operation(path)) from None
                time.sleep(2**attempt)

    def pages(self,path,params=None):
        page=1
        while True:
            values=self.request(path,{**(params or {}),"per_page":100,"page":page})
            if not isinstance(values,list):
                raise Failure("unexpected page","REST pagination")
            yield from values
            if len(values)<100:
                break
            page+=1

    def graph(self,query,**variables):
        result=self.request("graphql",data={"query":query,"variables":variables})
        if result.get("errors"):
            codes={e.get("type") or e.get("extensions",{}).get("code") or "query error" for e in result["errors"]}
            code=next((s for s in ("FORBIDDEN","NOT_FOUND","RATE_LIMITED") if s in codes),"query error")
            raise Failure(code,"GraphQL")
        if result.get("data") is None:
            raise Failure("missing result","GraphQL")
        return result["data"]


def connection(fetch):
    cursor=None
    seen=set()
    while True:
        result=fetch(cursor)
        yield from result["nodes"]
        if not result["pageInfo"]["hasNextPage"]:
            return
        cursor=result["pageInfo"]["endCursor"]
        if not cursor or cursor in seen:
            raise Failure("invalid cursor","GraphQL pagination")
        seen.add(cursor)


def search(api,endpoint,query,qualifier,start,end):
    """Search indexing has a 1000-record cap even with pagination. Subdivide to the second."""
    params={"q":query+" "+qualifier+":"+timestamp(start)+".."+timestamp(end),"per_page":100}
    page=1
    seen=set()
    while True:
        result=api.request("search/"+endpoint,{**params,"page":page})
        total=result["total_count"]
        if total>1000 or result.get("incomplete_results") is not False:
            if start >= end:
                raise Failure("saturated or incomplete one-second query","global search")
            mid=start+dt.timedelta(seconds=int((end-start).total_seconds())//2)
            yield from search(api,endpoint,query,qualifier,start,mid)
            yield from search(api,endpoint,query,qualifier,mid+dt.timedelta(seconds=1),end)
            return
        for item in result["items"]:
            key=(item["repository"]["id"],item["sha"]) if endpoint=="commits" else item["id"]
            if key not in seen:
                yield item
                seen.add(key)
        if page*100>=total:
            if len(seen)!=total:
                raise Failure("results changed during pagination","global search")
            return
        page+=1


def person(actor):
    return bool(actor and actor.get("login","").casefold()==OWNER.casefold()
                and actor.get("type",actor.get("__typename","User"))=="User")


def record(repo,kind,ident,date,url,title="",role="authored",branches=()):
    if kind not in TYPES or not date:
        raise Failure("invalid event","reconciliation")
    return {"repo_id":repo["id"],"type":kind,"id":str(ident),"sha":str(ident) if kind=="commit" else "",
            "date":timestamp(parse(date)),"html_url":url,"title":title,"role":role,
            "branches":sorted(set(branches)),"default_branch_member":repo["default_branch"] in branches}


def repo_meta(value):
    owner=value["owner"]["login"]
    visibility=value.get("visibility","private" if value["private"] else "public")
    return {"id":value["id"],"node_id":value["node_id"],"full_name":value["full_name"],"owner":owner,
            "owned":owner.casefold()==OWNER.casefold(),"private":bool(value["private"] or visibility!="public"),"html_url":value["html_url"],
            "visibility":visibility,
            "default_branch":value["default_branch"],"fork":value["fork"],"archived":value["archived"],
            "inventory_storage":value.get("description")==STATE_MARKER,
            "description":value.get("description") or "", "language":value.get("language"),
            "stars":value.get("stargazers_count",0),"forks":value.get("forks_count",0),
            "topics":value.get("topics",[]),"updated_at":value.get("updated_at"),"pushed_at":value.get("pushed_at"),
            "owner_type":value["owner"].get("type","Unknown"),"has_discussions":value.get("has_discussions",False),
            "created_at":value["created_at"],"scanned":False,"relationship":"accessible"}


CONTRIBUTED = """query($page:String){viewer{repositoriesContributedTo(first:100,after:$page,includeUserRepositories:true){
    nodes{databaseId nameWithOwner} pageInfo{hasNextPage endCursor}}}}"""
NATIVE_BY_REPO = """query($start:DateTime!,$end:DateTime!){viewer{contributionsCollection(from:$start,to:$end){
    commitContributionsByRepository(maxRepositories:100){repository{nameWithOwner}}
    issueContributionsByRepository(maxRepositories:100){repository{nameWithOwner}}
    pullRequestContributionsByRepository(maxRepositories:100){repository{nameWithOwner}}
    pullRequestReviewContributionsByRepository(maxRepositories:100){repository{nameWithOwner}}}}}"""
DISCUSSION_DISCOVERY = """query($q:String!,$cursor:String){search(type:DISCUSSION,query:$q,first:100,after:$cursor){
    discussionCount nodes{...on Discussion{repository{nameWithOwner}}} pageInfo{hasNextPage endCursor}}}"""
ORG_MEMBERSHIPS = "user/orgs"
QUERY_FIELDS = "oid url authoredDate committedDate messageHeadline messageBody parents(first:1){totalCount} author{user{login}} committer{user{login __typename}} authors(first:20){nodes{user{login}} "+PAGE+"}"
HISTORY = """query($id:ID!,$oid:GitObjectID!,$page:String){node(id:$id){...on Repository{object(oid:$oid){
    ...on Commit{history(first:100,after:$page){nodes{"""+QUERY_FIELDS+"} "+PAGE+"}}}}}}"
MORE_AUTHORS = """query($id:ID!,$oid:GitObjectID!,$page:String){node(id:$id){...on Repository{object(oid:$oid){
    ...on Commit{authors(first:100,after:$page){nodes{user{login}} """+PAGE+"}}}}}}"
DISCUSSIONS = """query($id:ID!,$page:String){node(id:$id){...on Repository{discussions(first:100,after:$page,
    orderBy:{field:UPDATED_AT,direction:DESC}){nodes{id title url createdAt updatedAt author{login __typename}} """+PAGE+"}}}}"


def discovery(clients,created,start,end,gaps,required_owners):
    repos={}
    by_name={}
    source_ids={source:set() for source in ("affiliation","personal public listing","organization listing",
        "GraphQL contributed repositories","annual GitHub contributions discovery","global issue/PR discovery",
        "global commit discovery","global authored discussion discovery","recent public event repository discovery")}
    def add(raw,api,source):
        repo=repo_meta(raw)
        rid=repo["id"]
        # Prefer the credential that actually listed the repository in its scoped inventory.
        if rid not in repos or source=="affiliation":
            repos[rid]=(repo,api)
            by_name[repo["full_name"].casefold()]=rid
        source_ids[source].add(rid)
        return rid
    def lookup(name,api,source):
        key=name.casefold()
        if key in by_name:
            source_ids[source].add(by_name[key])
            return
        try:
            add(api.request("repos/"+name),api,source)
        except Failure as exc:
            if exc.status not in (403,404):
                raise
            gaps.append({"source":source,"repository":name,"reason":str(exc),"status":"UNKNOWN"})
    for i,api in enumerate(clients):
        viewer=api.request("user")
        if not person(viewer):
            raise Failure("wrong account","collector identity")
        visible=[]
        for r in api.pages("user/repos",{"affiliation":"owner,collaborator,organization_member","visibility":"all"}):
            add(r,api,"affiliation")
            visible.append(r)
        if required_owners and not any(r["private"] and r["owner"]["login"].casefold()==required_owners[i].casefold() for r in visible):
            raise Failure("required private owner inaccessible","private scope")
        # Independent owner/organization endpoints include archived projects and forks.
        for r in api.pages(f"users/{OWNER}/repos",{"type":"owner"}):
            add(r,api,"personal public listing")
        orgs={r["owner"]["login"] for r in visible if r["owner"]["type"]=="Organization"}
        try:
            orgs.update(org["login"] for org in api.pages(ORG_MEMBERSHIPS))
        except Failure as exc:
            if exc.status!=403: raise
            gaps.append({"source":"organization memberships","status":"PARTIAL","reason":str(exc)})
        for org in orgs:
            for r in api.pages("orgs/"+org+"/repos",{"type":"all"}):
                add(r,api,"organization listing")
        try:
            for r in connection(lambda p:api.graph(CONTRIBUTED,page=p)["viewer"]["repositoriesContributedTo"]):
                if r:lookup(r["nameWithOwner"],api,"GraphQL contributed repositories")
            # Native contributions provide independent repository discovery, never personal totals.
            def native(left,right):
                groups=api.graph(NATIVE_BY_REPO,start=timestamp(left),end=timestamp(right))["viewer"]["contributionsCollection"]
                if any(len(values)>=100 for values in groups.values()):
                    if right-left<dt.timedelta(seconds=2):
                        raise Failure("saturated single-second result","native repository discovery")
                    mid=left+dt.timedelta(seconds=int((right-left).total_seconds())//2)
                    native(left,mid)
                    native(mid+dt.timedelta(seconds=1),right)
                    return
                for values in groups.values():
                    for value in values:
                        lookup(value["repository"]["nameWithOwner"],api,"annual GitHub contributions discovery")
            left=start
            while left<=end:
                right=min(end,dt.datetime(left.year,12,31,23,59,59,tzinfo=UTC))
                native(left,right)
                left=right+dt.timedelta(seconds=1)
        except Failure as exc:
            if exc.status!="FORBIDDEN":raise
            gaps.append({"source":"contributed repositories","status":"PARTIAL","reason":str(exc)})
        # Indexes complement the visible affiliated inventory and reveal outside collaborations.
        for expr,qualifier in typed_searches():
            for item in search(api,"issues",expr,qualifier,start,end):
                name=item["repository_url"].removeprefix("https://api.github.com/repos/")
                lookup(name,api,"global issue/PR discovery")
        for item in search(api,"commits","author:"+OWNER,"committer-date",start if start>created else dt.datetime(1970,1,1,tzinfo=UTC),end):
            lookup(item["repository"]["full_name"],api,"global commit discovery")
        def discussion_repos(left,right):
            query=f"author:{OWNER} created:{timestamp(left)}..{timestamp(right)}"
            page=api.graph(DISCUSSION_DISCOVERY,q=query,cursor=None)["search"]
            if page["discussionCount"]>1000:
                if right-left<dt.timedelta(seconds=2):
                    raise Failure("saturated single-second query","discussion discovery")
                mid=left+dt.timedelta(seconds=int((right-left).total_seconds())//2)
                discussion_repos(left,mid)
                discussion_repos(mid+dt.timedelta(seconds=1),right)
                return
            for node in connection(lambda cursor:page if cursor is None else api.graph(DISCUSSION_DISCOVERY,q=query,cursor=cursor)["search"]):
                if node and node.get("repository"):
                    lookup(node["repository"]["nameWithOwner"],api,"global authored discussion discovery")
        try:
            discussion_repos(start,end)
        except Failure as exc:
            if exc.status!="FORBIDDEN":raise
            gaps.append({"source":"public discussion discovery","status":"PARTIAL","reason":str(exc)})
        # Only an auxiliary route for recent outside release/discussion work. No event-feed counts are added.
        try:
            for item in api.pages(f"users/{OWNER}/events/public"):
                if person(item.get("actor")) and item.get("repo",{}).get("name"):
                    lookup(item["repo"]["name"],api,"recent public event repository discovery")
        except Failure as exc:
            if exc.status!=403:raise
            gaps.append({"source":"recent public event repository discovery","status":"PARTIAL","reason":str(exc)})
    return repos,source_ids


def commit_role(api,repo,item):
    primary=person((item.get("author") or {}).get("user"))
    rows=item["authors"]
    credited=any(person((x or {}).get("user")) for x in rows["nodes"])
    while rows["pageInfo"]["hasNextPage"] and not credited:
        rows=api.graph(MORE_AUTHORS,id=repo["node_id"],oid=item["oid"],page=rows["pageInfo"]["endCursor"])["node"]["object"]["authors"]
        credited=any(person((x or {}).get("user")) for x in rows["nodes"])
    return "authored" if primary else "coauthored" if credited else None


def profile_automation(api,repo,item):
    if repo["full_name"].casefold()!=PROFILE:
        return False
    if item["messageHeadline"]=="Refresh public repository snapshot":
        return True
    if item["messageHeadline"]!="Automated profile inventory snapshot" or not re.search(r"(?mi)^Automation: profile-history\s*$",item["messageBody"]):
        return False
    detail=api.request(f"repos/{repo['full_name']}/commits/{item['oid']}",{"per_page":100})
    files=detail.get("files",[])
    return bool(files) and all(f["filename"] in AUTOMATION_PATHS and f.get("previous_filename",f["filename"]) in AUTOMATION_PATHS for f in files)


def commits(api,repo,previous,prior_tips,force):
    branches=list(api.pages("repos/"+repo["full_name"]+"/branches"))
    heads={b["name"]:b["commit"]["sha"] for b in branches}
    tips=defaultdict(list)
    for branch,sha in heads.items():tips[sha].append(branch)
    found={}
    for tip,names in tips.items():
        prior_branch=next((b for b,sha in prior_tips.items() if sha==tip),None)
        if prior_branch is not None and not force:
            rows=[row.copy() for row in previous if prior_branch in row["branches"]]
        else:
            rows=[]
            def page(cursor):
                obj=api.graph(HISTORY,id=repo["node_id"],oid=tip,page=cursor)["node"]["object"]
                if not obj:
                    raise Failure("branch changed during scan","commit history")
                return obj["history"]
            for c in connection(page):
                role=commit_role(api,repo,c)
                if not role:continue
                title=c["messageHeadline"]
                if profile_automation(api,repo,c):
                    continue
                row=record(repo,"commit",c["oid"],c["authoredDate"],c["url"],title,role)
                row["committed_at"]=c["committedDate"]
                row["merge"]=c["parents"]["totalCount"]>1
                rows.append(row)
        for row in rows:
            if row["id"] not in found:
                row["branches"]=set()
                found[row["id"]]=row
            found[row["id"]]["branches"].update(names)
    for row in found.values():
        row["branches"]=sorted(row["branches"])
        row["default_branch_member"]=repo["default_branch"] in row["branches"]
    return list(found.values()),heads

def repo_events(api,repo,start,cutoff,previous_coverage):
    base="repos/"+repo["full_name"]
    rows=[]
    coverage={}
    def visit(source,fn):
        try:
            result=list(fn())
        except Failure as exc:
            if exc.status not in (403,404,409,410,"FORBIDDEN","NOT_FOUND"):
                raise
            coverage[source]=retained_source(previous_coverage.get(source,{}),cutoff,str(exc))
        else:
            rows.extend(result)
            coverage[source]={"status":"SCANNED"}
    def issues():
        for item in api.pages(base+"/issues",{"state":"all","since":start,"sort":"updated","direction":"desc"}):
            if "pull_request" in item or not person(item["user"]): continue
            yield record(repo,"issue",item["id"],item["created_at"],item["html_url"],item["title"],"opened")
    def prs_and_reviews():
        for pr in api.pages(base+"/pulls",{"state":"all","sort":"updated","direction":"desc"}):
            if pr["updated_at"]<start:return
            if person(pr["user"]):
                row=record(repo,"pr",pr["id"],pr["created_at"],pr["html_url"],pr["title"],"opened")
                row.update(base_ref=pr["base"]["ref"],head_ref=pr["head"]["ref"])
                yield row
            for review in api.pages(base+f"/pulls/{pr['number']}/reviews"):
                if person(review["user"]) and review.get("submitted_at"):
                    yield record(repo,"review",review["id"],review["submitted_at"],review["html_url"],
                                 pr["title"],"submitted")
    def comments(route,kind):
        for c in api.pages(base+route,{"since":start,"sort":"updated","direction":"asc"}):
            if person(c["user"]):
                issue=(c.get("issue_url") or c.get("pull_request_url","")).rsplit("/",1)[-1]
                yield record(repo,kind,c["id"],c["created_at"],c["html_url"],"Comment on #"+issue)
    def releases():
        for rel in api.pages(base+"/releases"):
            if person(rel["author"]):
                stamp=rel["published_at"] or rel["created_at"]
                yield record(repo,"release",rel["id"],stamp,rel["html_url"],rel["name"] or rel["tag_name"],"published")
    def discussions():
        for d in connection(lambda p:api.graph(DISCUSSIONS,id=repo["node_id"],page=p)["node"]["discussions"]):
            if d["updatedAt"]<start:return
            if person(d["author"]):
                yield record(repo,"discussion",d["id"],d["createdAt"],d["url"],d["title"],"opened")
    visit("issues",issues)
    visit("pull requests and submitted reviews",prs_and_reviews)
    visit("issue and PR conversation comments",lambda:comments("/issues/comments","issue_comment"))
    visit("inline PR review comments",lambda:comments("/pulls/comments","review_comment"))
    visit("releases",releases)
    if repo["has_discussions"]:
        visit("discussion topics",discussions)
    else:
        coverage["discussion topics"]={"status":"DISABLED","reason":"GitHub reports Discussions disabled."}
    return [r for r in rows if r["date"]<=cutoff],coverage


def retained_source(previous,attempt,reason):
    entry=deepcopy(previous)
    entry.update(status="UNKNOWN",reason=reason,last_attempt_at=attempt,
                 last_success_at=previous.get("last_success_at",previous.get("to")))
    return entry


def retain_inaccessible(repo,attempt,last_snapshot):
    retained=deepcopy(repo)
    retained.update(scanned=False,access_status="UNKNOWN",last_attempt_at=attempt,
                    last_success_at=repo.get("last_success_at",last_snapshot))
    # A previously public repository may now be private. Keep its old facts only in the owner inventory.
    retained.setdefault("last_known_visibility",repo["visibility"])
    retained.setdefault("last_known_private",repo["private"])
    retained.update(visibility="unknown",private=True)
    retained["source_coverage"]={name:retained_source(value,attempt,"Repository inaccessible to configured read credentials")
                                for name,value in repo.get("source_coverage",{}).items()}
    return retained


def optional_discovery(optional_clients,created,start,end,gaps):
    repos={}
    sources=defaultdict(set)
    accepted=[]
    for api in optional_clients:
        try:
            if api is None:
                raise Failure("credential not configured","optional collector")
            if not person(api.request("user")):
                raise Failure("unexpected account","optional collector")
            optional_gaps=[]
            found,source_ids=discovery([api],created,start,end,optional_gaps,None)
        except Failure as exc:
            gaps.append({"source":"optional collaborator credential","status":"UNKNOWN",
                         "reason":str(exc),"last_attempt_at":timestamp(end)})
            continue
        repos.update(found)
        for name,ids in source_ids.items():
            sources[name].update(ids)
        gaps.extend(optional_gaps)
        accepted.append(api)
    return repos,sources,accepted


def build(clients,previous,force=False,required_owners=None,storage_marker=STATE_MARKER,progress_path=None,optional_clients=(),
          collect_technologies=False):
    now=dt.datetime.now(UTC).replace(microsecond=0)
    key={"source":5,"base":(previous or {}).get("snapshot_at"),"force":force,"owners":required_owners and list(required_owners)}
    progress={}
    if progress_path and progress_path.is_file():
        stored=json.loads(progress_path.read_text(encoding="utf8"))
        if stored.get("key")==key and dt.timedelta(0)<=now-parse(stored["cutoff"])<DAY:
            progress=stored
            now=parse(stored["cutoff"])
    cutoff=timestamp(now)
    viewer=clients[0].request("user")
    if not person(viewer):
        raise Failure("wrong account","collector identity")
    created=parse(viewer["created_at"])
    if previous and (previous.get("schema")!=1 or previous["account"]!=OWNER):
        raise Failure("incompatible checkpoint","history inventory")
    if required_owners and len(required_owners)!=len(clients):
        raise Failure("missing owner-specific credential","private scope")
    full=not previous or force or previous.get("collection_revision")!=COLLECTION_REVISION or now-parse(previous["last_full_at"])>=7*DAY
    start=created if full else max(created,parse(previous["snapshot_at"])-2*DAY)
    gaps=[]
    repos,sources=discovery(clients,created,start,now,gaps,required_owners)
    extra,extra_sources,accepted=optional_discovery(optional_clients,created,start,now,gaps)
    for rid,value in extra.items():
        repos.setdefault(rid,value)
    for source,ids in extra_sources.items():
        sources.setdefault(source,set()).update(ids)
    lookup_clients=[*clients,*accepted]
    old_repos={r["id"]:r for r in (previous or {}).get("repositories",[])}
    missing=set(old_repos)-set(repos)
    if missing:
        # Outside collaborators with only historical activity may be absent in the incremental discovery window.
        for rid in missing:
            restored=False
            for api in lookup_clients:
                try:
                    raw=api.request("repositories/"+str(rid))
                except Failure as exc:
                    if exc.status in (403,404,410):continue
                    raise
                repos[rid]=(repo_meta(raw),api)
                restored=True
                break
            if not restored:
                repos[rid]=(retain_inaccessible(old_repos[rid],cutoff,previous["snapshot_at"]),None)
                gaps.append({"repo_id":rid,"source":"repository visibility","status":"UNKNOWN",
                    "reason":"Previously verified records retained; configured credentials cannot read current repository metadata.",
                    "last_success_at":repos[rid][0]["last_success_at"],"last_attempt_at":cutoff,
                    "required_action":"Select this repository in its owner's collector token and approve organization access. Contents, Issues and Pull requests require read access."})
    old_rows=defaultdict(list)
    for row in (previous or {}).get("records",[]):
        old_rows[row["repo_id"]].append(row)
    results=[]
    metadata=[]
    ids=sorted(repos)
    if progress.get("ids")!=ids:
        progress={"key":key,"cutoff":cutoff,"ids":ids,"entries":{}}
    stored=0
    total=len(repos)
    for idx,(rid,(repo,api)) in enumerate(sorted(repos.items()),1):
        if storage_marker and repo.get("inventory_storage") and repo["owned"] and repo["private"]:
            stored+=1
            continue
        if api is None:
            metadata.append(repo)
            results.extend(deepcopy(old_rows[rid]))
            continue
        cached=progress["entries"].get(str(rid))
        if cached and cached["repo"]["visibility"]==repo["visibility"] and cached["repo"]["full_name"]==repo["full_name"]:
            try:
                tips={b["name"]:b["commit"]["sha"] for b in api.pages("repos/"+repo["full_name"]+"/branches")}
            except Failure as exc:
                if exc.status not in (403,404,409,410): raise
                tips={} if exc.status==409 else None
            if tips==cached["repo"]["branch_heads"]:
                metadata.append(cached["repo"])
                results.extend(cached["records"])
                gaps.extend(cached["gaps"])
                print(f"History scan: resumed verified entry {idx}/{total}",flush=True)
                continue
        gap_offset=len(gaps)
        older=old_repos.get(rid,{})
        last_verified=older.get("last_success_at",(previous or {}).get("snapshot_at"))
        since=timestamp(min(start,parse(last_verified)-2*DAY)) if last_verified else timestamp(created)
        originals=old_rows[rid]
        # Preserve previously observed historical facts. Recompute branch membership for currently reachable commits.
        by_id={(r["type"],r["id"]):deepcopy(r) for r in originals}
        prior_commits=[r for r in originals if r["type"]=="commit"]
        try:
            current_commits,tips=commits(api,repo,prior_commits,older.get("branch_heads",{}),
                full or older.get("source_coverage",{}).get("reachable branch commits",{}).get("status")=="UNKNOWN")
            commit_status={"status":"SCANNED"}
        except Failure as exc:
            if exc.status==409 and not older.get("branch_heads"):
                current_commits,tips=[],{}
                commit_status={"status":"SCANNED","reason":"Empty repository"}
            elif exc.status in (403,404,410,"FORBIDDEN","NOT_FOUND"):
                current_commits,tips=[],deepcopy(older.get("branch_heads",{}))
                commit_status=retained_source(older.get("source_coverage",{}).get("reachable branch commits",{}),cutoff,str(exc))
            else:raise
        live_ids=set()
        for row in current_commits:
            if row["date"]>cutoff:
                # Revisit a future-author-dated commit's branches next run.
                for branch in row["branches"]:
                    tips.pop(branch,None)
                continue
            row["reachable"]=True
            by_id[("commit",row["id"])]=row
            live_ids.add(row["id"])
        for c in prior_commits:
            if c["id"] not in live_ids and commit_status["status"]=="SCANNED":
                archived=by_id[("commit",c["id"])]
                archived["reachable"]=False
                archived["branches"]=[]
                archived["default_branch_member"]=False
        changed,source_coverage=repo_events(api,repo,since,cutoff,older.get("source_coverage",{}))
        for row in changed:
            by_id[(row["type"],row["id"])]=row
        source_coverage["reachable branch commits"]=commit_status
        for source,entry in source_coverage.items():
            if entry["status"]=="UNKNOWN":
                gaps.append({"repo_id":rid,"source":source,"status":"UNKNOWN","reason":entry["reason"],
                             "last_success_at":entry.get("last_success_at"),"last_attempt_at":cutoff})
                continue
            entry.update({"from":since if source!="reachable branch commits" else "earliest reachable commit",
                          "to":cutoff,"last_success_at":cutoff,"last_attempt_at":cutoff,
                          "permission":("Contents read" if source in ("releases","reachable branch commits")
                          else "Discussions read" if source=="discussion topics" else
                          "Pull requests read" if "review" in source else "Issues and Pull requests read")})
            if entry["status"]=="PARTIAL":
                gaps.append({"repo_id":rid,"source":source,"status":"PARTIAL","reason":entry["reason"]})
        repo["scanned"]=all(s["status"] in ("SCANNED","DISABLED") for s in source_coverage.values())
        repo["last_attempt_at"]=cutoff
        repo["last_success_at"]=cutoff if repo["scanned"] else last_verified
        repo["relationship"]=("owned" if repo["owned"] else "organization contributor" if by_id and repo["owner_type"]=="Organization"
                              else "collaborator" if by_id else "accessible")
        repo["source_coverage"]=source_coverage
        repo["branch_heads"]=tips
        repo["contributed"]=bool(by_id)
        repo["discovery_sources"]=sorted(source for source,ids in sources.items() if rid in ids)
        metadata.append(repo)
        results.extend(by_id.values())
        if progress_path:
            progress["entries"][str(rid)]={"repo":repo,"records":list(by_id.values()),"gaps":gaps[gap_offset:]}
            atomic(progress_path,progress)
        if idx%5==0 or idx==total:
            print(f"History scan: {idx}/{total} repository entries processed",flush=True)
    results.sort(key=lambda r:(r["date"],r["repo_id"],r["type"],r["id"]))
    standard_gaps=[
        "Deleted or inaccessible repositories, deleted events and commits unreachable from every currently visible branch cannot be reconstructed before first observation.",
        "GitHub search discovers indexed default-branch commits. Outside public work limited to unindexed branches or coauthorship may be undiscoverable unless another source reveals the repository.",
        "Authenticated affiliations, independent owner and organization inventories, and contribution-index/search results cover only authorized visibility.",
        "GitHub's short-lived Events feed is not used for historical totals. Discussion replies, review reactions, gists, packages and unlinked authorship are not claimed."
    ]
    partial_sources={gap["source"] for gap in gaps}
    source_list=[{"source":name,"repositories":len(ids),"status":"PARTIAL" if name in partial_sources else "SCANNED",
                "from":("GitHub-retained recent window" if name=="recent public event repository discovery" else timestamp(start)),
                "to":cutoff,"permission":"account-visible repository metadata and GitHub search"} for name,ids in sorted(sources.items())]
    state = {"schema":1,"collection_revision":COLLECTION_REVISION,"account":OWNER,"account_created_at":timestamp(created),"snapshot_at":cutoff,
            "last_attempt_at":cutoff,"last_success_at":timestamp(dt.datetime.now(UTC)),
            "last_full_at":cutoff if full else previous["last_full_at"],
            "repositories":metadata,"records":results,
            "coverage":{"status":"PARTIAL","discovered":len(metadata),"scanned":sum(r["scanned"] for r in metadata),
                        "storage_repositories_excluded":stored,"sources":source_list,"gaps":gaps,
                        "limitations":standard_gaps,"mode":"full" if full else "incremental",
                        "earliest_record":results[0]["date"] if results else None}}
    if collect_technologies:
        prior = (previous or {}).get("technology_inventory")
        state["technology_inventory"] = technologies.collect(((repo, repos[repo["id"]][1]) for repo in metadata), prior)
    elif previous and "technology_inventory" in previous:
        state["technology_inventory"] = previous["technology_inventory"]
    return state


def atomic(path,state):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf8",delete=False,dir=path.parent) as temp:
        json.dump(state,temp,ensure_ascii=False,separators=(",",":"))
        temp.flush()
        os.fsync(temp.fileno())
    os.replace(temp.name,path)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--previous",type=Path)
    p.add_argument("--full",action="store_true")
    args=p.parse_args()
    output=args.output.resolve()
    checkout=Path(__file__).resolve().parents[1]
    if output.is_relative_to(checkout) or (args.previous and args.previous.resolve().is_relative_to(checkout)):
        raise Failure("private inventory must stay outside checkout","output isolation")
    previous_path=args.previous or output
    previous=json.loads(previous_path.read_text(encoding="utf8")) if previous_path.is_file() else None
    tokens=[os.getenv(k) for k in ("PROFILE_ACTIVITY_READ_TOKEN","PROFILE_ACTIVITY_ORG_READ_TOKEN")]
    if not all(tokens):
        raise Failure("both owner-scoped read credentials required","private scope")
    attempt=output.with_name("history-attempt.json")
    atomic(attempt,{"attempt_at":timestamp(dt.datetime.now(UTC)),"success":False,
                    "last_success":previous["snapshot_at"] if previous else None})
    progress_path=output.with_name("inventory.partial.json")
    optional_token=os.getenv("SKILLAURA_PROFILE_TOKEN")
    state=build([GitHub(t) for t in tokens],previous,args.full,(OWNER,"Evisionindia"),progress_path=progress_path,
                optional_clients=[GitHub(optional_token) if optional_token else None], collect_technologies=True)
    atomic(output,state)
    progress_path.unlink(missing_ok=True)
    atomic(attempt,{"attempt_at":state["last_attempt_at"],"success":True,"last_success":state["snapshot_at"]})
    print("Owner inventory validated; public output must be rendered separately.")


if __name__=="__main__":
    try:
        main()
    except Failure as exc:
        sys.exit(str(exc))
    except Exception as exc:
        sys.exit(f"Owner inventory incomplete ({unexpected_failure_category(exc)}); prior snapshot preserved.")
