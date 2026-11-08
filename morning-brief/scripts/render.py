"""Render the morning brief from a JSON data file.

Usage: python3 render.py data.json out.html
The page design lives here so every run renders the same way; a run only
gathers, sorts, and writes data.json (schema at the end of SKILL.md).
"""
import base64, html, json, os, sys, urllib.parse, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
sys.path.insert(0, HERE)

def e(s): return html.escape(str(s or ""), quote=True)

def font(name):
    with open(os.path.join(ASSETS, "fonts", name), "rb") as f:
        return base64.b64encode(f.read()).decode()

def seed_href(seed):
    return "https://claude.ai/new?q=" + urllib.parse.quote(seed, safe="") + "&surface=cowork&composer=mini"

def hero_image(d):
    """Use your own photos in assets/paintings when present, else paint a landscape.

    Photos are grouped by mood (OPEN, NORMAL, HEAVY) and rotate by date, so
    consecutive days with the same mood never show the same photo until the
    group has been used up.
    """
    import datetime
    mood = d.get("day_class", "OPEN")
    meta_path = os.path.join(ASSETS, "paintings", "paintings.json")
    if os.path.exists(meta_path):
        allp = json.load(open(meta_path))
        group = [m for m in allp if m.get("mood") == mood] or allp
        if group:
            day = datetime.date.fromisoformat(d["date_iso"]).toordinal()
            pick = group[day % len(group)]
            with open(os.path.join(ASSETS, "paintings", pick["file"]), "rb") as f:
                b = base64.b64encode(f.read()).decode()
            ext = "png" if pick["file"].endswith(".png") else "jpeg"
            return f"data:image/{ext};base64,{b}", pick.get("credit", ""), pick["file"]
    from paint import data_uri
    return data_uri(d["date_iso"], mood), "", None

def para(it):
    before, link, after, url = it.get("before", ""), it.get("link_text", ""), it.get("after", ""), it.get("url")
    mid = f'<a class="src" href="{e(url)}" target="_blank" rel="noopener">{e(link)}</a>' if (link and url) else e(link)
    return f"<p>{e(before)}{mid}{e(after)}</p>"

def title(it):
    t = e(it["title"])
    day = f'<span class="carry">Day {int(it["days_shown"])}</span>' if it.get("days_shown", 1) > 1 else ""
    if it.get("url"):
        t = f'<a href="{e(it["url"])}" target="_blank" rel="noopener">{t}</a>'
    return f'<h3>{t}{day}</h3>'

def stamp(btn, cls=""):
    """No action links: links that start a new Claude chat do not open from the published page."""
    return ""

def why(it):
    return ""

def check(it):
    return (f'<button class="check" type="button" aria-pressed="false" data-key="{e(it["key"])}" '
            f'aria-label="Mark done: {e(it["title"])}"></button>')

def todo(it, lst="needs", with_para=True):
    return (f'<li class="todo" data-list="{lst}" data-key="{e(it["key"])}">{check(it)}<div class="todo-body">{title(it)}'
            f'{para(it) if with_para else ""}{why(it)}{stamp(it.get("button"), "small")}</div></li>')

def plain(it, mark=""):
    m = f'<span class="mark" aria-hidden="true">{mark}</span>' if mark else ""
    return f'<li class="plain">{m}<div>{title(it)}{para(it)}{stamp(it.get("button"), "small")}</div></li>'

def row(label, inner, cls=""):
    return f'<section class="row {cls}"><h2>{e(label)}</h2><div class="content">{inner}</div></section>'

def render(d):
    img, credit, used_file = hero_image(d)
    f600, f600i, f400i = font("fraunces-latin-600-normal.woff2"), font("fraunces-latin-600-italic.woff2"), font("fraunces-latin-400-italic.woff2")
    rows = []
    wk = d.get("worth_knowing", {}) or {}
    if wk.get("weather"):
        extra = "".join(f'<p>{e(x)}</p>' for x in wk.get("weather_extra", []))
        rows.append(f'<section class="row lead"><h2>Weather</h2><div class="content weather"><p>{e(wk["weather"])}</p>{extra}</div></section>')
    one = d.get("one_thing")
    if one:
        rows.append(f'''<section class="row feature"><h2>The one thing</h2>
<div class="content todo one" data-list="needs" data-key="{e(one["key"])}"><div class="one-head">{check(one)}{title(one)}</div>{para(one)}{stamp(one.get("button"))}</div></section>''')
    needs = d.get("needs", [])
    if one or needs:
        lst = f'<ul class="todos" data-list="needs">{"".join(todo(i) for i in needs)}</ul>' if needs else ""
        rows.append(f'<section class="row"><h2>Needs you <span class="count" data-count="needs"></span></h2>'
                    f'<div class="content">{lst}<p class="all-done" data-done="needs" hidden>Nothing needs you this morning.</p></div></section>')
    day = d.get("day", [])
    if day or d.get("day_note"):
        cells = f'<h2>Your day</h2><div class="content">' + (f'<p class="note">{e(d["day_note"])}</p>' if d.get("day_note") else "") + "</div>"
        for x in day:
            rng = f'<p class="range">{e(x["range"])}</p>' if x.get("range") else ""
            cells += (f'<div class="chip"><span class="t">{e(x["time"])}</span><span class="n">{e(x["title"])}</span></div>'
                      f'<div class="content detail">{title(x)}{rng}{para(x) if x.get("before") or x.get("link_text") else ""}'
                      f'{stamp(x.get("button"), "small right")}</div>')
        rows.append(f'<section class="row day">{cells}</section>')
    res = d.get("resolved", [])
    if res: rows.append(row("Already sorted", '<ul class="plainlist">' + "".join(plain(i, "✓") for i in res) + "</ul>"))
    pr = d.get("priorities", [])[:3]
    if pr:
        n = len(pr); word = {1: "It is done.", 2: "Both are done.", 3: "All three are done."}[n]
        rows.append(f'<section class="row"><h2>Top priorities <span class="count" data-count="prio"></span></h2><div class="content">'
                    f'<ul class="todos" data-list="prio">{"".join(todo(i, "prio", False) for i in pr)}</ul>'
                    f'<p class="all-done" data-done="prio" hidden>{word}</p></div></section>')
    blocks = []
    if wk.get("coming_up"):
        lines = "".join(f'<li><span class="lead-in">{e(c["lead"])}</span> {e(c["rest"])}</li>' for c in wk["coming_up"][:6])
        blocks.append(f'<div class="wk wide"><h4>Coming up</h4><ul>{lines}</ul></div>')
    if wk.get("sports"):
        def sl(x):
            t = f'<a href="{e(x["url"])}" target="_blank" rel="noopener">{e(x["matchup"])}</a>' if x.get("url") else e(x["matchup"])
            return f'<li><span class="lead-in">{t}</span>{e(x.get("rest", ""))}</li>'
        blocks.append(f'<div class="wk wide"><h4>Sports</h4><ul>{"".join(sl(x) for x in wk["sports"][:8])}</ul></div>')
    if blocks:
        rows.append(f'<section class="row worth"><h2>Worth knowing</h2><div class="content wk-grid">{"".join(blocks)}</div></section>')
    for s in d.get("sections", []):
        if not s.get("items") and not s.get("note"): continue
        inner = (f'<p class="note">{e(s["note"])}</p>' if s.get("note") else "") + \
                '<ul class="plainlist">' + "".join(plain(i) for i in s.get("items", [])) + "</ul>"
        rows.append(row(s["heading"], inner))
    if not one and not needs and not res:
        rows.insert(0, row("Today", '<p class="note">Nothing needs you this morning.</p>'))
    srcs = d.get("sources", [])
    src_txt = ", ".join(srcs[:-1]) + (" and " + srcs[-1] if len(srcs) > 1 else (srcs[0] if srcs else ""))
    page = TEMPLATE.format(
        f600=f600, f600i=f600i, f400i=f400i, img=img, weekday=e(d["weekday"]), date_rail=e(d["date_rail"]),
        time_rail=e(d["time_rail"]), date_long=e(d["date_long"]), caption=e(d["caption"]), credit=(f'<p class="credit">{e(credit)}</p>' if credit else ""),
        rows="\n".join(rows), name=e(d["name"]), sources=e(src_txt), date_iso=e(d["date_iso"]))
    return page, used_file

TEMPLATE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>The {weekday} Brief, {date_long}</title>
<style>
@font-face{{font-family:"Fraunces";font-weight:600;font-style:normal;font-display:block;src:url(data:font/woff2;base64,{f600}) format("woff2");}}
@font-face{{font-family:"Fraunces";font-weight:600;font-style:italic;font-display:block;src:url(data:font/woff2;base64,{f600i}) format("woff2");}}
@font-face{{font-family:"Fraunces";font-weight:400;font-style:italic;font-display:block;src:url(data:font/woff2;base64,{f400i}) format("woff2");}}
:root{{--bg:#101010;--surface:#1D1D1D;--surface-2:#242424;--ink:#E8E5E1;--ink-soft:#9A9690;--ink-faint:#5A5651;--gilt:#F7D046;--gilt-hover:#FFDD63;--on-gilt:#1B1606;--veil:rgba(0,0,0,.42);
 --serif:"Fraunces",Georgia,"Times New Roman",serif;--sans:-apple-system,"Segoe UI",Inter,Roboto,sans-serif;--col:1014px;
 box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px);color-scheme:dark;}}
@media (prefers-color-scheme:light){{:root:not([data-theme="dark"]){{--bg:#F3F1EC;--surface:#FFFFFF;--surface-2:#ECE9E2;--ink:#1E1C19;--ink-soft:#5F5B55;--ink-faint:#A19C93;--gilt:#F2C230;--gilt-hover:#E6B41F;--veil:rgba(30,26,20,.28);color-scheme:light;}}}}
:root[data-theme="light"]{{--bg:#F3F1EC;--surface:#FFFFFF;--surface-2:#ECE9E2;--ink:#1E1C19;--ink-soft:#5F5B55;--ink-faint:#A19C93;--gilt:#F2C230;--gilt-hover:#E6B41F;--veil:rgba(30,26,20,.28);color-scheme:light;}}
html{{scroll-padding-top:env(safe-area-inset-top,0px);background:var(--bg);}}
*,*::before,*::after{{box-sizing:border-box;}}
body{{margin:0;background:var(--bg);color:var(--ink-soft);font-family:var(--sans);font-size:15.5px;line-height:1.62;-webkit-font-smoothing:antialiased;}}
a{{color:inherit;}}
:focus-visible{{outline:2px solid var(--gilt);outline-offset:3px;border-radius:6px;}}
.page{{padding:34px 24px 64px;transition:filter .25s ease;}}
body.dim .page{{filter:blur(3px) brightness(.6);}}
.sun{{display:block;margin:0 auto 22px;width:26px;height:26px;color:var(--ink);}}
.hero{{display:grid;grid-template-columns:1fr minmax(0,var(--col)) 1fr;column-gap:clamp(20px,4vw,60px);align-items:center;}}
.rail{{font-family:var(--serif);font-style:italic;font-weight:600;color:var(--ink);font-size:clamp(30px,3.1vw,44px);line-height:1;writing-mode:vertical-rl;white-space:nowrap;}}
.rail.left{{transform:rotate(180deg);justify-self:end;}}
.rail.right{{justify-self:start;}}
figure{{margin:0;}}
.frame{{position:relative;overflow:hidden;aspect-ratio:1.93/1;background:var(--surface);}}
.frame img{{display:block;width:100%;height:100%;object-fit:cover;}}
.frame::after{{content:"";position:absolute;inset:0;background:radial-gradient(ellipse 62% 48% at 50% 52%,rgba(15,12,6,.52),rgba(15,12,6,.18) 70%,rgba(15,12,6,.08));pointer-events:none;}}
.masthead{{position:absolute;inset:0;z-index:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:var(--gilt);
 text-shadow:0 2px 24px rgba(20,14,4,.7),0 1px 3px rgba(20,14,4,.6);padding:0 4%;}}
.masthead .the{{font-family:var(--serif);font-style:italic;font-weight:600;font-size:clamp(28px,5.6vw,74px);line-height:.92;}}
.masthead h1{{margin:0;font-family:var(--serif);font-weight:600;font-size:clamp(40px,8.9vw,116px);line-height:.98;letter-spacing:-.015em;}}
figcaption{{display:flex;justify-content:space-between;gap:28px;margin-top:10px;align-items:baseline;}}
.caption{{font-family:var(--serif);font-style:italic;font-weight:400;color:var(--ink-soft);font-size:15px;line-height:1.5;max-width:62ch;margin:0;}}
.credit{{font-family:var(--serif);font-style:italic;font-size:11px;letter-spacing:.06em;color:var(--ink-faint);text-align:right;flex-shrink:0;max-width:40ch;margin:0;}}
main{{max-width:var(--col);margin:44px auto 0;}}
.row{{display:grid;grid-template-columns:minmax(0,40fr) minmax(0,60fr);column-gap:32px;row-gap:26px;padding:0 30px;align-items:start;}}
.row+.row{{margin-top:60px;}}
.feature{{position:relative;background:var(--surface);border-radius:12px;padding:30px;}}
h2{{margin:0;font-family:var(--serif);font-style:italic;font-weight:400;font-size:24px;line-height:1.25;color:var(--ink);}}
h3{{margin:0 0 6px;font-family:var(--sans);font-size:17px;font-weight:500;color:var(--ink);line-height:1.35;}}
h3 a{{text-decoration:none;}}
h3 a:hover{{text-decoration:underline;text-underline-offset:3px;text-decoration-thickness:1px;}}
.carry{{margin-left:10px;font-family:var(--serif);font-style:italic;font-weight:400;font-size:14px;color:var(--gilt);}}
.content p{{margin:0;max-width:64ch;}}
.src{{color:var(--ink-soft);text-decoration:underline;text-decoration-color:var(--ink-faint);text-underline-offset:3px;text-decoration-thickness:1px;}}
.src:hover{{color:var(--ink);}}
ul{{list-style:none;margin:0;padding:0;}}
.todos li,.plainlist li{{display:flex;gap:14px;align-items:flex-start;}}
.todos li+li,.plainlist li+li{{margin-top:28px;}}
.check{{flex:none;width:20px;height:20px;margin-top:2px;border-radius:50%;border:1.5px solid var(--ink-faint);background:transparent;cursor:pointer;position:relative;padding:0;}}
.check:hover{{border-color:var(--gilt);}}
.check[aria-pressed="true"]{{background:var(--gilt);border-color:var(--gilt);}}
.check[aria-pressed="true"]::after{{content:"";position:absolute;left:6px;top:3px;width:5px;height:10px;border:solid var(--on-gilt);border-width:0 2px 2px 0;transform:rotate(45deg);}}
.todo.done h3{{text-decoration:line-through;text-decoration-color:var(--ink-faint);color:var(--ink-soft);}}
.todo.done p{{opacity:.45;}}
.all-done{{margin-top:26px !important;font-family:var(--serif);font-style:italic;font-size:19px;color:var(--gilt);}}
.mark{{flex:none;width:20px;text-align:center;font-weight:700;color:var(--gilt);}}
.note{{color:var(--ink-soft);margin:0 !important;}}
.note+ul{{margin-top:22px;}}
.chip{{display:flex;gap:12px;align-items:baseline;padding:2px 0 2px 14px;border-left:2px solid var(--gilt);min-width:0;}}
.chip .t{{flex:none;font-family:var(--serif);font-style:italic;font-size:13px;color:var(--ink-faint);}}
.chip .n{{font-size:14px;font-weight:400;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.range{{font-family:var(--serif);font-style:italic;color:var(--ink);font-size:15px;margin:-2px 0 6px !important;}}
.detail{{display:flex;flex-direction:column;}}
.act-line{{margin:10px 0 0 !important;}}
.act{{font-family:var(--serif);font-style:italic;font-size:16px;color:var(--gilt);text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:4px;text-decoration-color:color-mix(in srgb,var(--gilt) 45%,transparent);}}
.act:hover{{text-decoration-color:var(--gilt);}}
.one .act-line{{margin-left:34px !important;}}
.todo.done .act-line{{opacity:.45;}}
.count{{font-family:var(--sans);font-style:normal;font-size:13px;color:var(--ink-faint);margin-left:8px;white-space:nowrap;}}
.one-head{{display:flex;gap:14px;align-items:flex-start;}}
.one .one-head+p{{margin-left:34px;}}
.one.done h3{{text-decoration:line-through;text-decoration-color:var(--ink-faint);color:var(--ink-soft);}}
.one.done p{{opacity:.45;}}

.wk-grid{{display:grid;grid-template-columns:1fr 1fr;gap:28px 32px;}}
.wk.wide{{grid-column:1/-1;}}
.wk h4{{margin:0 0 6px;font-family:var(--serif);font-style:italic;font-size:18px;font-weight:400;color:var(--ink);}}
.wk p,.wk li{{font-size:15px;color:var(--ink-soft);margin:0;}}
.wk li+li{{margin-top:6px;}}
.wk .lead-in{{color:var(--ink);}}
.weather p{{font-family:var(--serif);font-style:italic;font-size:19px;line-height:1.5;color:var(--ink);max-width:56ch;}}
.weather p+p{{font-size:16px;color:var(--ink-soft);margin-top:6px !important;}}
.wk a{{text-decoration:none;}} .wk a:hover{{text-decoration:underline;text-underline-offset:3px;}}
footer{{display:flex;justify-content:center;align-items:center;gap:10px;text-align:center;margin-top:84px;font-family:var(--serif);font-style:italic;font-size:21px;line-height:1.45;color:var(--ink-soft);padding:0 12px;}}
footer strong{{font-weight:400;color:var(--ink);}}
.spark{{width:24px;height:24px;color:var(--gilt);flex:none;}}
.veil{{position:fixed;inset:0;z-index:10;display:grid;place-items:center;background:var(--veil);padding:20px;}}
.veil[hidden]{{display:none;}}
.dialog{{position:relative;width:min(348px,100%);background:var(--surface);border-radius:12px;padding:32px 30px 30px;text-align:center;}}
.dialog .close{{position:absolute;top:10px;right:10px;width:32px;height:32px;border:0;border-radius:50%;background:transparent;color:var(--ink-soft);font-size:20px;line-height:1;cursor:pointer;}}
.dialog .close:hover{{color:var(--ink);background:var(--surface-2);}}
.dialog .seal{{width:46px;height:46px;margin:0 auto 16px;border-radius:50%;background:var(--gilt);display:grid;place-items:center;position:relative;}}
.dialog .seal::before{{content:"";position:absolute;inset:4px;border-radius:50%;border:1.2px dashed rgba(27,22,6,.42);}}
.dialog .seal svg{{width:18px;height:18px;}}
.dialog h2{{font-size:25px;line-height:1.2;margin:0 0 12px;}}
.dialog p{{margin:0;font-size:15px;color:var(--ink-soft);}}
@media (prefers-reduced-motion:reduce){{.page{{transition:none;}}}}
@media (max-width:1180px){{.hero{{grid-template-columns:44px minmax(0,1fr) 44px;}}}}
@media (max-width:760px){{
 .hero{{grid-template-columns:1fr;row-gap:8px;}}
 .rail{{writing-mode:horizontal-tb;transform:none !important;justify-self:start !important;font-size:22px;}}
 .rail.left{{order:-2;}} .rail.right{{order:-1;font-size:15px;color:var(--ink-soft);margin-bottom:6px;}}
 .frame{{aspect-ratio:4/3;}}
 figcaption{{flex-direction:column;gap:6px;}} .credit{{text-align:left;}}
 .row{{grid-template-columns:1fr;padding:0 2px;row-gap:16px;}}
 .row+.row{{margin-top:48px;}}
 .feature{{padding:24px 22px;}}
 .day .chip{{margin-top:10px;}} .day .detail{{margin-top:-4px;}}
 footer{{font-size:18px;}}
 .wk-grid{{grid-template-columns:1fr;}}
 .one .one-head+p,.one .act-line{{margin-left:0 !important;}}
}}
</style></head>
<body><div class="page">
<svg class="sun" viewBox="0 0 26 26" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M5 19a8 8 0 0 1 16 0z" fill="currentColor"/><path d="M2 19h22M13 6V3M5.5 9.5 3.6 7.6M20.5 9.5l1.9-1.9"/></svg>
<header class="hero">
 <div class="rail left" aria-hidden="true">{date_rail}</div>
 <figure>
  <div class="frame"><img src="{img}" alt=""><div class="masthead"><span class="the">The</span><h1>{weekday} Brief</h1></div></div>
  <figcaption><p class="caption">{caption}</p>{credit}</figcaption>
 </figure>
 <div class="rail right" aria-hidden="true">{time_rail}</div>
</header>
<main>
{rows}
<footer><span>Made for {name} by Claude</span><svg class="spark" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5c.5 4.6 2.4 6.5 7 7-4.6.5-6.5 2.4-7 7-.5-4.6-2.4-6.5-7-7 4.6-.5 6.5-2.4 7-7z" fill="currentColor"/></svg></footer>
</main>
</div>
<div class="veil" hidden>
 <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="done-h" aria-describedby="done-p">
  <button class="close" type="button" aria-label="Close">&times;</button>
  <div class="seal" aria-hidden="true"><svg viewBox="0 0 18 18" fill="none" stroke="#1B1606" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9.5l3.2 3L14 5.5"/></svg></div>
  <h2 id="done-h">Nothing left<br>on the list.</h2>
  <p id="done-p">The rest of the day is yours.</p>
 </div>
</div>
<script>
(function(){{
 var DAY="{date_iso}", KEY="morning-brief-"+DAY, GKEY="morning-brief-done", state={{}}, everDone={{}}, dbRef=null, doneRef=null, writing=false, again=false;
 // everDone holds every key ticked on any day ({{key: date}}), so a carried-over item stays ticked on later pages.
 try{{state=JSON.parse(localStorage.getItem(KEY)||"{{}}")||{{}};}}catch(e){{state={{}};}}
 try{{everDone=JSON.parse(localStorage.getItem(GKEY)||"{{}}")||{{}};}}catch(e){{everDone={{}};}}
 Object.keys(everDone).forEach(function(k){{state[k]=1;}});
 function saveLocal(){{try{{localStorage.setItem(KEY,JSON.stringify(state));localStorage.setItem(GKEY,JSON.stringify(everDone));}}catch(e){{}}}}
 async function saveDb(){{
  if(!dbRef) return; if(writing){{again=true;return;}}
  writing=true;
  try{{ do{{ again=false;
   await dbRef.set({{date:DAY,done:Object.assign({{}},state),updated:new Date().toISOString()}});
   if(doneRef) await doneRef.set({{keys:Object.assign({{}},everDone),updated:new Date().toISOString()}});
  }}while(again); }}catch(e){{}}
  writing=false;
 }}
 var items=[].slice.call(document.querySelectorAll(".todo[data-key]"));
 var veil=document.querySelector(".veil"),closeBtn=veil.querySelector(".close"),opener=null;
 function inList(l){{return items.filter(function(x){{return x.getAttribute("data-list")===l;}});}}
 function apply(li,on){{li.classList.toggle("done",on);li.querySelector(".check").setAttribute("aria-pressed",on?"true":"false");}}
 function applyAll(){{items.forEach(function(li){{apply(li,!!state[li.getAttribute("data-key")]);}});sync();}}
 function sync(){{
  ["needs","prio"].forEach(function(l){{
   var xs=inList(l); if(!xs.length) return;
   var open=xs.filter(function(x){{return !x.classList.contains("done");}}).length;
   var c=document.querySelector('[data-count="'+l+'"]'); if(c) c.textContent=open+" of "+xs.length+" open";
   var done=document.querySelector('[data-done="'+l+'"]'), ul=document.querySelector('ul[data-list="'+l+'"]');
   if(done) done.hidden=open!==0; if(ul) ul.hidden=open===0;
  }});
 }}
 function allNeedsDone(){{var xs=inList("needs");return xs.length&&xs.every(function(x){{return x.classList.contains("done");}});}}
 function openD(from){{opener=from;veil.hidden=false;document.body.classList.add("dim");closeBtn.focus();}}
 function closeD(){{veil.hidden=true;document.body.classList.remove("dim");if(opener&&opener.offsetParent)opener.focus();}}
 closeBtn.addEventListener("click",closeD);
 veil.addEventListener("click",function(ev){{if(ev.target===veil)closeD();}});
 document.addEventListener("keydown",function(ev){{if(!veil.hidden&&(ev.key==="Escape"||ev.key==="Tab")){{ev.preventDefault();if(ev.key==="Escape")closeD();else closeBtn.focus();}}}});
 items.forEach(function(li){{
  var b=li.querySelector(".check"),k=li.getAttribute("data-key");
  b.addEventListener("click",function(){{var on=!li.classList.contains("done");apply(li,on);if(on){{state[k]=1;everDone[k]=everDone[k]||DAY;}}else{{delete state[k];delete everDone[k];}}
   saveLocal();saveDb();sync();if(on&&li.getAttribute("data-list")==="needs"&&allNeedsDone())openD(b);}});
 }});
 applyAll();
 // Ticks also go to the brief's private store, so the next run can read them.
 (async function(){{
  try{{
   if(!window.claude||!window.claude.use) return;
   var user=await window.claude.use("user"), db=await window.claude.use("db");
   if(!user||!db) return;
   var uid=await user.id(); if(!uid) return;
   var col=db.collection("data/users/"+uid);
   var ref=col.doc("ticks-"+DAY), dref=col.doc("done");
   var before=JSON.stringify(state)+JSON.stringify(everDone);
   var snap=await ref.get(), dsnap=await dref.get(), remote={{}}, rDone={{}};
   if(snap.exists){{remote=(snap.data()||{{}}).done||{{}};}}
   if(dsnap.exists){{rDone=(dsnap.data()||{{}}).keys||{{}};}}
   Object.keys(rDone).forEach(function(k){{if(!everDone[k])everDone[k]=rDone[k];}});
   Object.keys(remote).forEach(function(k){{state[k]=1;if(!everDone[k])everDone[k]=DAY;}});
   Object.keys(everDone).forEach(function(k){{state[k]=1;}});
   saveLocal();applyAll();
   dbRef=ref; doneRef=dref;
   // Push anything ticked before the store loaded, or held only on this device.
   var localOnly=Object.keys(state).some(function(k){{return !remote[k];}})||Object.keys(everDone).some(function(k){{return !rDone[k];}});
   if(localOnly||before!==JSON.stringify(state)+JSON.stringify(everDone)&&!snap.exists) saveDb();
  }}catch(e){{}}
 }})();
}})();
</script>
</body></html>'''

if __name__ == "__main__":
    data = json.load(open(sys.argv[1]))
    page, used = render(data)
    open(sys.argv[2], "w").write(page)
    print(json.dumps({"out": sys.argv[2], "bytes": len(page), "painting_file": used}))
