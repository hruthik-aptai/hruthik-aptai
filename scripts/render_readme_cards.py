#!/usr/bin/env python3
"""Render the animated SVG cards for the profile README.

Writes every card into cards/. Each card carries its own background and both
colour schemes (a prefers-color-scheme block inside the SVG), so it reads on
GitHub's light and dark themes and can still sit inside a plain <a><img></a>
link. (GitHub splits a <picture> out of its link, so linked cards can't use it.)

  python3 scripts/render_readme_cards.py            animated cards
  STATIC=1 python3 scripts/render_readme_cards.py   every card at its final frame

Env:
  CONTRIB_JSON  contribution data (default data/contributions.json, the GraphQL
                contributionCalendar response the workflow saves)
  OUT_DIR       where to write cards (default cards/)

Standard library only, so the workflow needs no installs. Fonts are pre-subset
WOFF2 files in fonts/ (see scripts/subset_fonts.sh), embedded as data URIs because
an SVG inside <img> can't fetch anything.
"""
import base64
import datetime as dt
import json
import os
import re
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
STATIC = os.environ.get("STATIC") == "1"
DATA = Path(os.environ.get("CONTRIB_JSON", ROOT / "data" / "contributions.json"))
OUT = Path(os.environ.get("OUT_DIR", ROOT / "cards"))

W = 840
PAD = 36

# AptAI brand tokens, from aptaisystems.com (light and dark). Cards refer to them
# as CSS variables; card() writes both sets into the SVG.
THEMES = {
    "light": dict(
        bg="#FFFCF0", panel="#F5F0DF", ink="#252422", muted="#6E6A63", accent="#00CFC0",
        accent_ink="#045660", soft="#DCFAF8", line="#E8E2CE", line2="#C8C2AA",
        heat=["#EFE9D5", "#BDF1EC", "#6ADDD3", "#00BFB1", "#045660"], bar="#B4ECE6",
    ),
    "dark": dict(
        bg="#1B1A17", panel="#232119", ink="#FFFCF0", muted="#9A9288", accent="#00CFC0",
        accent_ink="#2FE0D3", soft="#0C3533", line="#2C2A26", line2="#3D3A34",
        heat=["#2A2824", "#0C3533", "#045660", "#00A99D", "#2FE0D3"], bar="#13504D",
    ),
}

FONT_FILES = {"D": "display", "DI": "display-italic", "B": "body", "BS": "body-semibold", "M": "mono"}
FONT_STACK = {
    "D": "D,Georgia,serif", "DI": "DI,Georgia,serif", "B": "B,system-ui,sans-serif",
    "BS": "BS,system-ui,sans-serif", "M": "M,ui-monospace,Menlo,monospace",
}
_font_cache = {}

TOKENS = {k: f"var(--{k.replace('_', '-')})" for k in THEMES["light"] if k != "heat"}
TOKENS["heat"] = [f"var(--h{i})" for i in range(5)]


def theme_vars(name):
    t = THEMES[name]
    pairs = [(k.replace("_", "-"), v) for k, v in t.items() if k != "heat"]
    pairs += [(f"h{i}", c) for i, c in enumerate(t["heat"])]
    return ";".join(f"--{k}:{v}" for k, v in pairs)


def inline_vars(svg):
    """Presentation attributes can't take var(), so move fill/stroke vars into style."""
    def fix(m):
        tag = m.group(0)
        props = re.findall(r' (fill|stroke)="(var\(--[a-z0-9-]+\))"', tag)
        if not props:
            return tag
        tag = re.sub(r' (fill|stroke)="var\(--[a-z0-9-]+\)"', "", tag)
        decl = ";".join(f"{k}:{v}" for k, v in props)
        if ' style="' in tag:
            return tag.replace(' style="', f' style="{decl};', 1)
        end = -2 if tag.endswith("/>") else -1
        return tag[:end] + f' style="{decl}"' + tag[end:]
    return re.sub(r"<[a-z]+ [^>]*>", fix, svg)


def font_face(key):
    if key not in _font_cache:
        raw = (ROOT / "fonts" / f"{FONT_FILES[key]}.woff2").read_bytes()
        b64 = base64.b64encode(raw).decode()
        _font_cache[key] = f"@font-face{{font-family:'{key}';src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
    return _font_cache[key]


KEYFRAMES = """
@keyframes up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pop{0%{opacity:0;transform:scale(.2)}70%{opacity:1;transform:scale(1.15)}100%{opacity:1;transform:scale(1)}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes wipe{from{transform:scaleX(1)}to{transform:scaleX(0)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
@keyframes ring{0%{opacity:.7;transform:scale(1)}100%{opacity:0;transform:scale(3)}}
@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}
.up{animation:up .7s cubic-bezier(.2,.7,.2,1) both}
.fade{animation:fade .6s ease-out both}
.pop{transform-box:fill-box;transform-origin:center;animation:pop .45s ease-out both}
.grow{transform-box:fill-box;transform-origin:bottom;animation:grow .9s cubic-bezier(.2,.7,.2,1) both}
.wipe{transform-box:fill-box;transform-origin:right;transform:scaleX(0)}
.pulse{animation:pulse 2.4s ease-in-out infinite}
.ring{transform-box:fill-box;transform-origin:center;opacity:0;animation:ring 2.4s ease-out infinite}
.blink{animation:blink 1s step-end infinite}
.travel{opacity:0}
@media (prefers-reduced-motion:reduce){
  *{animation:none!important}
  .cu{visibility:hidden!important}
  .fin{visibility:visible!important}
}
"""


def card(name, w, h, title, body, fonts, extra_css=""):
    t = TOKENS
    css = f"svg{{{theme_vars('light')}}}@media (prefers-color-scheme:dark){{svg{{{theme_vars('dark')}}}}}"
    css += "".join(font_face(f) for f in fonts)
    css += "".join(f".{k.lower()}{{font-family:{FONT_STACK[k]}}}" for k in fonts)
    if not STATIC:
        css += KEYFRAMES + extra_css
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-labelledby="title"><title id="title">{escape(title)}</title>'
        f"<style>{css}</style>"
        f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="18" fill="{t["bg"]}" stroke="{t["line"]}" stroke-width="2"/>'
        f"{body}</svg>"
    )
    svg = inline_vars(svg)
    path = OUT / f"{name}.svg"
    path.write_text(svg, encoding="utf-8")
    return path


def anim(cls, delay):
    """class + delay attributes for an entrance animation, or nothing in STATIC mode."""
    if STATIC:
        return ""
    return f' class="{cls}" style="animation-delay:{delay:.2f}s"'


def loop(cls, delay=None):
    """class attribute for a looping animation, or nothing in STATIC mode."""
    if STATIC:
        return ""
    return f' class="{cls}"' + (f' style="animation-delay:{delay:.2f}s"' if delay is not None else "")


def text(x, y, s, font, size, fill, anchor="start", extra=""):
    return (
        f'<text x="{x}" y="{y}" class="{font.lower()}" font-size="{size}" fill="{fill}" '
        f'text-anchor="{anchor}"{extra}>{escape(s)}</text>'
    )


def count_up(x, y, value, fmt, font, size, fill, anchor, begin, dur=1.1, frames=16):
    """A number that counts up with SMIL <set> frames (CSS can't change text)."""
    final = escape(fmt(value))
    attrs = f'x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}"'
    if STATIC or value == 0:
        return f'<text class="{font.lower()}" {attrs}>{final}</text>'
    vals, seen = [], set()
    for i in range(frames):
        p = i / frames
        v = int(round(value * (1 - (1 - p) ** 3)))
        if v not in seen and v != value:
            seen.add(v)
            vals.append((i, v))
    step = dur / frames
    out = []
    for n, (i, v) in enumerate(vals):
        start = begin + i * step
        nxt = vals[n + 1][0] if n + 1 < len(vals) else frames
        out.append(
            f'<text class="cu {font.lower()}" {attrs} visibility="hidden">'
            f'<set attributeName="visibility" to="visible" begin="{start:.3f}s" dur="{(nxt - i) * step:.3f}s"/>'
            f"{escape(fmt(v))}</text>"
        )
    out.append(
        f'<text class="fin {font.lower()}" {attrs} visibility="hidden">'
        f'<set attributeName="visibility" to="visible" begin="{begin + dur:.3f}s" fill="freeze"/>{final}</text>'
    )
    return "".join(out)


# ---------------------------------------------------------------- data

def load_days():
    raw = json.loads(DATA.read_text())
    cal = raw["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    levels = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
    weeks = []
    for wk in cal["weeks"]:
        weeks.append([
            dict(date=dt.date.fromisoformat(d["date"]), n=d["contributionCount"],
                 level=levels.get(d.get("contributionLevel"), 0), weekday=d.get("weekday", 0))
            for d in wk["contributionDays"]
        ])
    return cal["totalContributions"], weeks


def stats(total, weeks):
    days = [d for wk in weeks for d in wk]
    days.sort(key=lambda d: d["date"])
    active = sum(1 for d in days if d["n"] > 0)
    busiest = max(days, key=lambda d: (d["n"], d["date"]))
    # Current streak: consecutive active days ending today, or yesterday if today is still empty.
    streak, i = 0, len(days) - 1
    if i >= 0 and days[i]["n"] == 0:
        i -= 1
    while i >= 0 and days[i]["n"] > 0:
        streak += 1
        i -= 1
    months = {}
    for d in days:
        key = (d["date"].year, d["date"].month)
        months[key] = months.get(key, 0) + d["n"]
    return dict(total=total, active=active, busiest=busiest, streak=streak,
                months=sorted(months.items()), first=days[0]["date"], last=days[-1]["date"])


fmt_int = lambda v: f"{v:,}"


# ---------------------------------------------------------------- cards

STAGES = ["Signal", "Enrich", "Score", "Approve", "Sequence", "Booked"]


def hero():
    t = TOKENS
    h = 300
    b = []
    # Label row with a live dot, like the "Running" badge on aptaisystems.com.
    b.append(f'<g{anim("fade", 0)}>')
    if not STATIC:
        b.append(f'<circle cx="{PAD + 5}" cy="47" r="5" fill="{t["accent"]}" class="ring"/>')
    b.append(f'<circle cx="{PAD + 5}" cy="47" r="5" fill="{t["accent"]}"{loop("pulse")}/>')
    b.append(text(PAD + 20, 52, "APTAI SYSTEMS", "M", 14, t["accent_ink"], extra=' letter-spacing="2.5"'))
    b.append(text(W - PAD, 52, "aptaisystems.com ↗", "M", 14, t["muted"], "end"))
    b.append("</g>")
    b.append(f'<g{anim("up", .15)}>' + text(PAD - 2, 128, "Hruthik Varma", "D", 64, t["ink"]) + "</g>")
    b.append(
        f'<g{anim("up", .35)}><text x="{PAD}" y="172" font-size="23" fill="{t["muted"]}" class="b">'
        f'Building outbound systems that run on '
        f'<tspan class="di" fill="{t["ink"]}" font-size="25">market and CRM data</tspan>.</text></g>'
    )
    # The engine, left to right, with a pulse that runs along it.
    y = 238
    n = len(STAGES)
    cw, gap = 116, (W - 2 * PAD - n * 116) / (n - 1)
    b.append(f'<line x1="{PAD}" y1="{y}" x2="{W - PAD}" y2="{y}" stroke="{t["line2"]}" stroke-width="1.5" stroke-dasharray="3 5"{anim("fade", .5)}/>')
    if not STATIC:
        b.append(
            f'<circle cx="{PAD}" cy="{y}" r="4" fill="{t["accent"]}" class="travel" '
            f'style="animation:travel 3.2s cubic-bezier(.5,0,.5,1) 2s infinite"/>'
        )
    for i, s in enumerate(STAGES):
        x = PAD + i * (cw + gap)
        last = i == n - 1
        fill, stroke, ink = (t["soft"], t["accent"], t["accent_ink"]) if last else (t["bg"], t["line2"], t["ink"])
        b.append(f'<g{anim("up", .6 + i * .12)}>')
        b.append(f'<rect x="{x:.1f}" y="{y - 19}" width="{cw}" height="38" rx="19" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        b.append(text(f"{x + 18:.1f}", y + 5, f"0{i + 1}", "M", 12, t["muted"]))
        b.append(text(f"{x + 42:.1f}", y + 5, s, "M", 14, ink))
        b.append("</g>")
    extra = f"@keyframes travel{{0%{{opacity:0;transform:translateX(0)}}8%{{opacity:1}}92%{{opacity:1}}100%{{opacity:0;transform:translateX({W - 2 * PAD}px)}}}}"
    return card("hero", W, h, "Hruthik Varma, AptAI Systems", "".join(b), ["D", "DI", "B", "M"], extra)


MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def graph(total, weeks):
    t = TOKENS
    h = 262
    cell, step = 11.5, 13.9
    x0, y0 = PAD + 40, 104
    base = .2
    b = [f'<g{anim("fade", base)}>',
         text(PAD, 52, "CONTRIBUTIONS", "M", 14, t["accent_ink"], extra=' letter-spacing="2.5"'),
         text(PAD, 76, "Last 12 months on GitHub", "B", 17, t["muted"]), "</g>"]
    b.append(f'<g{anim("up", base)}>')
    b.append(count_up(W - PAD, 66, total, fmt_int, "D", 44, t["ink"], "end", base + .2, 1.6))
    b.append("</g>")
    # Month labels where a new month starts in the first row.
    seen = None
    for c, wk in enumerate(weeks):
        m = wk[0]["date"].month
        if m != seen and wk[0]["date"].day <= 7 and c < len(weeks) - 2:
            b.append(text(f"{x0 + c * step:.1f}", y0 - 8, MONTHS[m - 1], "M", 12, t["muted"]))
        seen = m
    for r, lbl in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        b.append(text(PAD, f"{y0 + r * step + 9.5:.1f}", lbl, "M", 12, t["muted"]))
    for c, wk in enumerate(weeks):
        for d in wk:
            r = d["weekday"]
            delay = base + .3 + c * .022 + r * .03
            b.append(
                f'<rect x="{x0 + c * step:.1f}" y="{y0 + r * step:.1f}" width="{cell}" height="{cell}" rx="2.5" '
                f'fill="{t["heat"][d["level"]]}"{anim("pop", delay)}/>'
            )
    # Legend
    ly = y0 + 7 * step + 22
    lx = W - PAD - 5 * step - 44
    b.append(f'<g{anim("fade", base + 1.6)}>')
    b.append(text(lx - 10, ly + 10, "Less", "M", 12, t["muted"], "end"))
    for i in range(5):
        b.append(f'<rect x="{lx + i * step:.1f}" y="{ly}" width="{cell}" height="{cell}" rx="2.5" fill="{t["heat"][i]}"/>')
    b.append(text(lx + 5 * step + 6, ly + 10, "More", "M", 12, t["muted"]))
    b.append("</g>")
    return card("contributions", W, h, f"{total:,} contributions in the last year", "".join(b), ["B", "D", "M"])


def months(s):
    t = TOKENS
    h = 330
    base = .6
    b = [f'<g{anim("fade", base)}>',
         text(PAD, 52, "PER MONTH", "M", 14, t["accent_ink"], extra=' letter-spacing="2.5"'),
         text(PAD, 76, f"{MONTHS[s['first'].month - 1]} {s['first'].year} to {MONTHS[s['last'].month - 1]} {s['last'].year}", "B", 17, t["muted"]),
         "</g>"]
    # Stats, two by two on the left.
    busy = s["busiest"]
    cells = [
        ("Total", s["total"], fmt_int, None),
        ("Current streak", s["streak"], lambda v: f"{v:,}", "days" if s["streak"] != 1 else "day"),
        ("Active days", s["active"], fmt_int, None),
        ("Busiest day", busy["n"], fmt_int, f'{busy["date"].day} {MONTHS[busy["date"].month - 1]}'),
    ]
    for i, (label, val, f, unit) in enumerate(cells):
        cx = PAD + (i % 2) * 150
        cy = 140 + (i // 2) * 96
        d = base + .2 + i * .12
        b.append(f'<g{anim("up", d)}>')
        b.append(text(cx, cy - 26, label.upper(), "M", 11, t["muted"], extra=' letter-spacing="1.2"'))
        b.append(count_up(cx, cy + 14, val, f, "D", 38, t["ink"], "start", d + .1, 1.0, 12))
        if unit:
            b.append(text(cx, cy + 38, unit, "B", 15, t["muted"]))
        b.append("</g>")
    # Bars
    data = s["months"]
    bx0, bx1 = 340, W - PAD
    base_y, top = 268, 108
    step = (bx1 - bx0) / len(data)
    bw = min(26, step * .62)
    peak = max(v for _, v in data) or 1
    best = max(range(len(data)), key=lambda i: (data[i][1], i))
    b.append(f'<line x1="{bx0}" y1="{base_y}" x2="{bx1}" y2="{base_y}" stroke="{t["line2"]}" stroke-width="1.5"{anim("fade", base)}/>')
    for i, ((yr, mo), v) in enumerate(data):
        x = bx0 + i * step + (step - bw) / 2
        bh = max(2.5, (base_y - top) * v / peak) if v else 2.5
        is_best = i == best and v > 0
        fill = t["accent"] if is_best else t["bar"]
        d = base + .35 + i * .07
        b.append(f'<rect x="{x:.1f}" y="{base_y - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="4" fill="{fill}"{anim("grow", d)}/>')
        lbl = MONTHS[mo - 1][0] if step < 30 else MONTHS[mo - 1]
        b.append(text(f"{x + bw / 2:.1f}", base_y + 24, lbl, "M", 12, t["accent_ink"] if is_best else t["muted"], "middle"))
        if is_best:
            b.append(f'<g{anim("up", d + .8)}>')
            b.append(text(f"{x + bw / 2:.1f}", f"{base_y - bh - 14:.1f}", f"{v:,}", "M", 14, t["accent_ink"], "middle"))
            b.append("</g>")
            b.append(f'<g{anim("fade", d + 1)}>' + text(f"{x + bw / 2:.1f}", base_y + 46, "best", "M", 11, t["accent_ink"], "middle") + "</g>")
    return card("months", W, h, "Contributions per month", "".join(b), ["B", "D", "M"])


TILES = [
    ("01", "OUTBOUND", ["Built from", "your data"], "aptaisystems.com", "signal"),
    ("02", "PRIVATE EQUITY", ["Origination", "for PE"], "/private-equity", "rings"),
    ("03", "FIELD NOTES", ["Playbooks", "and guides"], "/resources", "lines"),
]


def tile(idx):
    t = TOKENS
    num, label, title, link, motif = TILES[idx]
    w, h = 270, 250
    p = 24
    base = 1.0 + idx * .15
    b = [f'<g{anim("fade", base)}>',
         text(p, 44, num, "M", 13, t["accent_ink"]),
         text(p + 28, 44, label, "M", 13, t["muted"], extra=' letter-spacing="1.5"'),
         "</g>"]
    # A small motif per tile, top right.
    mx, my = w - p - 70, 76
    if motif == "signal":
        pts = [(mx, my + 22), (mx + 35, my + 8), (mx + 70, my + 22)]
        b.append(f'<polyline points="{" ".join(f"{a},{c}" for a, c in pts)}" fill="none" stroke="{t["line2"]}" stroke-width="1.5"{anim("fade", base + .2)}/>')
        for k, (a, c) in enumerate(pts):
            col = t["accent"] if k == 2 else t["line2"]
            b.append(f'<circle cx="{a}" cy="{c}" r="6" fill="{t["bg"]}" stroke="{col}" stroke-width="2"{anim("pop", base + .3 + k * .15)}/>')
        b.append(f'<circle cx="{pts[2][0]}" cy="{pts[2][1]}" r="2.5" fill="{t["accent"]}"{loop("pulse")}/>')
    elif motif == "rings":
        cx, cy = mx + 45, my + 14
        for k, r in enumerate((24, 15, 6)):
            col = t["accent"] if r == 6 else t["line2"]
            fill = t["accent"] if r == 6 else "none"
            b.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{col}" stroke-width="1.5"{anim("pop", base + .3 + k * .15)}/>')
        if not STATIC:
            b.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="{t["accent"]}" class="ring" style="animation-delay:{base + .8:.2f}s"/>')
    else:
        for k, ln in enumerate((70, 52, 62)):
            col = t["accent"] if k == 0 else t["line2"]
            b.append(f'<rect x="{mx}" y="{my + k * 12}" width="{ln}" height="4" rx="2" fill="{col}"{anim("fade", base + .3 + k * .15)}/>')
    for k, ln in enumerate(title):
        b.append(f'<g{anim("up", base + .25 + k * .1)}>' + text(p - 1, 160 + k * 36, ln, "D", 33, t["ink"]) + "</g>")
    b.append(f'<g{anim("fade", base + .6)}>' + text(p, h - 26, f"{link} ↗", "M", 13, t["accent_ink"]) + "</g>")
    return card(f"tile-{idx + 1}", w, h, " ".join(title), "".join(b), ["D", "M"])


TERM = [
    ("$ ls", "cmd"),
    ("AGENTS.md  SOUL.md  USER.md", "hot"),
    ("TOOLS.md   MEMORY.md  skills/", "hot"),
    ("# loaded every session, kept small", "note"),
    ("docs/  data/  config/  scripts/", "cold"),
    ("# read only when the task needs it", "note"),
    ("$", "cmd"),
]


def minify():
    t = TOKENS
    h = 310
    base = 1.5
    b = [f'<g{anim("fade", base)}>',
         text(PAD, 52, "PUBLIC REPO", "M", 14, t["accent_ink"], extra=' letter-spacing="2.5"'), "</g>",
         f'<g{anim("up", base + .1)}>', text(PAD - 1, 112, "Mini-fy", "D", 52, t["ink"]), "</g>",
         f'<g{anim("up", base + .25)}>',
         text(PAD, 152, "A lean OpenClaw workspace pack", "B", 19, t["muted"]),
         text(PAD, 178, "for agents in the terminal.", "B", 19, t["muted"]),
         "</g>",
         f'<g{anim("up", base + .4)}>',
         f'<text x="{PAD}" y="222" font-size="19" fill="{t["ink"]}" class="di">More shipped work per token,</text>',
         f'<text x="{PAD}" y="246" font-size="19" fill="{t["ink"]}" class="di">per minute, per context window.</text>',
         "</g>",
         ]
    # Terminal panel
    px, py, pw, ph = 452, 36, W - PAD - 452, h - 72
    b.append(f'<g{anim("fade", base + .2)}>')
    b.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="12" fill="{t["panel"]}" stroke="{t["line"]}" stroke-width="1.5"/>')
    for k in range(3):
        b.append(f'<circle cx="{px + 20 + k * 16}" cy="{py + 20}" r="4.5" fill="{t["line2"]}"/>')
    b.append(text(px + pw - 16, py + 25, "Mini-fy", "M", 12, t["muted"], "end"))
    b.append("</g>")
    ly = py + 62
    tstart = base + .6
    for k, (ln, kind) in enumerate(TERM):
        col = {"cmd": t["accent_ink"], "hot": t["ink"], "cold": t["muted"], "note": t["muted"]}[kind]
        y = ly + k * 25
        b.append(text(px + 20, y, ln, "M", 13.5, col, extra=' xml:space="preserve" style="white-space:pre"'))
        if not STATIC:
            dur = .05 * len(ln)
            b.append(
                f'<rect x="{px + 16}" y="{y - 15}" width="{pw - 24}" height="21" fill="{t["panel"]}" class="wipe" '
                f'style="animation:wipe {dur:.2f}s steps({len(ln)}) {tstart:.2f}s both"/>'
            )
            tstart += dur + .12
    cy = ly + (len(TERM) - 1) * 25
    b.append(f'<rect x="{px + 34}" y="{cy - 14}" width="8" height="17" fill="{t["accent"]}"'
             f'{loop("blink", tstart)}/>')
    return card("minify", W, h, "Mini-fy, a lean OpenClaw workspace pack", "".join(b), ["D", "DI", "B", "M"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    total, weeks = load_days()
    s = stats(total, weeks)
    written = []
    written.append(hero())
    written.append(graph(total, weeks))
    written.append(months(s))
    for i in range(len(TILES)):
        written.append(tile(i))
    written.append(minify())
    for p in written:
        print(f"{p.relative_to(OUT.parent) if OUT.parent in p.parents else p}  {p.stat().st_size / 1024:.1f} KB")
    print(f"total {s['total']:,}  streak {s['streak']}  active {s['active']}  busiest {s['busiest']['n']} on {s['busiest']['date']}")


if __name__ == "__main__":
    main()
