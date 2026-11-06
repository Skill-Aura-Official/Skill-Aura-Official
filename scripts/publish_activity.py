"""Publish an already-sanitized PNG into the inactive release slot, then switch the stable URL."""
import hashlib
import io
import json
import os
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, HTTPRedirectHandler, build_opener

from activity_image import render

REPO = "Skill-Aura-Official/Skill-Aura-Official"
API = "https://api.github.com/repos/" + REPO
STABLE = "https://github.com/" + REPO + "/releases/latest/download/activity.png"
SLOTS = ("profile-activity-a","profile-activity-b")
MARKER = "Anonymous personal activity graphic for the SkillAura profile."
AGENT = "SkillAura-profile-image"


class StripAuth(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        redirected=super().redirect_request(req,fp,code,msg,headers,newurl)
        if urlparse(newurl).scheme != "https":
            raise RuntimeError("Unsafe redirect")
        if urlparse(newurl).hostname != urlparse(req.full_url).hostname:
            redirected.remove_header("Authorization")
        return redirected


opener=build_opener(StripAuth)


def request(url, method="GET", body=None, token=None, content_type=None, accept="application/vnd.github+json"):
    headers={"User-Agent":AGENT,"Accept":accept}
    if token:
        if urlparse(url).hostname not in ("api.github.com","uploads.github.com"):
            raise ValueError("Unexpected authenticated hostname")
        headers["Authorization"]="Bearer "+token
    if isinstance(body,dict):
        body=json.dumps(body).encode()
        content_type="application/json"
    if content_type:
        headers["Content-Type"]=content_type
    with opener.open(Request(url,data=body,headers=headers,method=method),timeout=30) as response:
        return response.read(4_000_000)


def endpoint(path,token,method="GET",body=None):
    result=request(API+"/"+path,method,body,token)
    return json.loads(result) if result else None


def choose_slot(releases,latest_id):
    if any(r["tag_name"] not in SLOTS or r["body"] != MARKER or r.get("immutable") for r in releases):
        raise RuntimeError("Release namespace not reserved for profile activity")
    current=next((r for r in releases if r["id"]==latest_id),None)
    if latest_id and not current:
        raise RuntimeError("Unexpected latest release")
    tag=SLOTS[1] if current and current["tag_name"]==SLOTS[0] else SLOTS[0]
    return tag,next((r for r in releases if r["tag_name"]==tag),None)


class ImageSource(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=="img" and attrs.get("data-canonical-src",attrs.get("src"))==STABLE:
            self.urls.append(attrs["src"])


def confirm_visitor(data):
    parser=ImageSource()
    parser.feed(request("https://github.com/Skill-Aura-Official",accept="text/html").decode())
    if len(parser.urls)!=1:
        raise RuntimeError("Expected one guest profile image")
    src=parser.urls[0]
    if src!=STABLE and urlparse(src).hostname!="camo.githubusercontent.com":
        raise RuntimeError("Unexpected profile image host")
    for attempt in range(14):
        try:
            received=request(src,accept="image/png")
            if received==data:
                return
        except HTTPError:
            pass
        if attempt in (0,5) and urlparse(src).hostname=="camo.githubusercontent.com":
            try:
                request(src,method="PURGE")
            except HTTPError:
                pass
        time.sleep(15)
    raise RuntimeError("Guest image did not match staged data before timeout")


def publish(state,token,sha):
    image=io.BytesIO()
    render(state).save(image,format="PNG")
    data=image.getvalue()
    digest="sha256:"+hashlib.sha256(data).hexdigest()
    releases=endpoint("releases?per_page=100",token)
    try:
        latest=endpoint("releases/latest",token)
    except HTTPError as exc:
        if exc.code!=404:
            raise
        latest=None
    tag,slot=choose_slot(releases,latest["id"] if latest else None)
    if not slot:
        slot=endpoint("releases",token,"POST",{"tag_name":tag,"target_commitish":sha,
                      "name":"Profile activity "+tag[-1].upper(),"body":MARKER,"draft":True,"make_latest":"false"})
    # No active asset is altered. Stage and verify before switching the latest-release pointer.
    if latest and latest["id"]==slot["id"]:
        raise RuntimeError("Refusing to replace active image")
    for asset in slot["assets"]:
        if asset["name"]!="activity.png":
            raise RuntimeError("Foreign asset in reserved release")
        endpoint(f"releases/assets/{asset['id']}",token,"DELETE")
    upload=f"https://uploads.github.com/repos/{REPO}/releases/{slot['id']}/assets?name=activity.png"
    asset=json.loads(request(upload,"POST",data,token,"image/png"))
    if asset["state"]!="uploaded" or asset["size"]!=len(data) or asset.get("digest")!=digest:
        raise RuntimeError("Uploaded image integrity mismatch")
    stored=request(f"{API}/releases/assets/{asset['id']}",token=token,accept="application/octet-stream")
    if stored!=data:
        raise RuntimeError("Staged asset bytes mismatch")
    endpoint(f"releases/{slot['id']}",token,"PATCH",{"draft":False,"make_latest":"true"})
    try:
        if endpoint("releases/latest",token)["id"]!=slot["id"]:
            raise RuntimeError("Stable release pointer did not switch")
        confirm_visitor(data)
    except Exception:
        if latest:
            endpoint(f"releases/{latest['id']}",token,"PATCH",{"make_latest":"true"})
        raise
    print(f"Guest image verified at {STABLE}; source {state['as_of']}; {digest}")


if __name__=="__main__":
    try:
        if os.environ["GITHUB_REPOSITORY"]!=REPO or os.environ["GITHUB_REF"]!="refs/heads/main":
            raise RuntimeError("Wrong publication target")
        publish(json.loads(Path("output/aggregate.json").read_text()),os.environ["GITHUB_TOKEN"],os.environ["GITHUB_SHA"])
    except HTTPError as exc:
        sys.exit(f"Profile image publication failed: HTTP {exc.code}")
    except Exception as exc:
        sys.exit(str(exc) if isinstance(exc,RuntimeError) else "Profile image publication failed.")
