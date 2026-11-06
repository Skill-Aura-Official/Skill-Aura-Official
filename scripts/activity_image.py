"""Render just anonymous counters and UTC timestamps at a size that works on phones."""
import datetime as dt
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from activity import validate

SCALE = 3
WIDTH, HEIGHT = 346, 145
INK, SECONDARY, RULE = "#172a33", "#394e59", "#cbd8db"


def font(size, bold=False):
    choices = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
               "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf")
    location = next((path for path in choices if Path(path).is_file()), None)
    if not location:
        raise ValueError("Approved readable system font missing")
    return ImageFont.truetype(location, size*SCALE)


def render(state):
    validate(state)
    image = Image.new("RGB",(WIDTH*SCALE,HEIGHT*SCALE),"#f4f8f8")
    draw = ImageDraw.Draw(image)
    def label(x,y,text,size,color=INK,bold=False,anchor="lm"):
        draw.text((x*SCALE,y*SCALE),text,font=font(size,bold),fill=color,anchor=anchor)
    label(12,11,"Last 30 UTC days",15,bold=True)
    columns = [(139,"commits","Commits"),(196,"pull_requests","PRs"),(252,"issues","Issues"),(309,"reviews","Reviews")]
    for x,_,name in columns:
        label(x,31,name,13,SECONDARY,anchor="mm")
    draw.line((12*SCALE,42*SCALE,334*SCALE,42*SCALE),fill=RULE,width=SCALE)
    for y,scope in [(54,"public"),(76,"private")]:
        label(12,y,scope.title(),15,bold=True)
        for x,key,_ in columns:
            unknown = scope=="private" and state["coverage"]=="PRIVATE_UNKNOWN"
            value = "—" if unknown else str(sum(row[scope][key] for row in state["days"].values()))
            label(x,y,value,15,bold=True,anchor="mm")
    partial = "Partial" if state["coverage"]=="VISIBLE_PRIVATE_SUBSET" else "Unavailable"
    label(12,98,"Private coverage: "+partial,12,SECONDARY)
    stamp=dt.datetime.fromisoformat(state["as_of"].replace("Z","+00:00"))
    label(12,116,stamp.strftime("Collected %d %b %Y, %H:%M UTC"),13)
    label(12,119,(stamp+dt.timedelta(minutes=45)).strftime("Stale after %d %b, %H:%M UTC"),12,SECONDARY)
    return image
