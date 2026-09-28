"""Static homepage: a full-screen, Reels-style feed of every story, with an info sheet for the channel."""

from __future__ import annotations

import html
import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Config
from .cover import cover_url
from .texts import mmss, render, spoken_date

CSS = """
:root{--bg:#000;--fg:#fff;--muted:rgba(255,255,255,.66);--faint:rgba(255,255,255,.45);--glass:rgba(255,255,255,.16);
--glass-hover:rgba(255,255,255,.28);--sheet:#1c1c1e;--sheet-2:#2c2c2e;--line:rgba(255,255,255,.12);--accent:#c77dff;
--font:-apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",system-ui,sans-serif;
--font-display:-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",system-ui,sans-serif;color-scheme:dark}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 var(--font);-webkit-font-smoothing:antialiased;overflow:hidden}
a{color:var(--accent)}button{font:inherit;color:inherit}
:focus-visible{outline:2px solid #fff;outline-offset:2px}
.app{position:relative;max-width:480px;height:100vh;height:100dvh;margin:0 auto}
.feed{height:100%;overflow-y:scroll;scroll-snap-type:y mandatory;overscroll-behavior:contain;scrollbar-width:none}
.feed::-webkit-scrollbar{display:none}
.reel{position:relative;height:100%;scroll-snap-align:start;scroll-snap-stop:always;overflow:hidden;cursor:pointer;
display:flex;flex-direction:column;padding:78px 22px 30px}
.reel-bg{position:absolute;inset:-60px;background:#2c2c2e center/cover;filter:blur(40px) saturate(1.3);transform:scale(1.15)}
.reel-shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.4) 0%,rgba(0,0,0,.12) 35%,rgba(0,0,0,.82) 100%)}
.reel-center{position:relative;flex:1;display:grid;place-items:center;min-height:0}
.reel-art{width:min(68vw,290px);max-height:100%;aspect-ratio:1;border-radius:16px;object-fit:cover;
box-shadow:0 20px 50px rgba(0,0,0,.5);background:linear-gradient(135deg,#8a2ecb,#e0477a);font-size:5rem;color:#fff}
.reel-art.ph{display:grid;place-items:center;font-weight:700}
.reel.on .reel-art{animation:reel-in .45s ease-out}
@keyframes reel-in{from{transform:scale(.94);opacity:.6}to{transform:none;opacity:1}}
.reel-info{position:relative;padding-right:58px}
.reel-new{display:inline-block;margin-bottom:10px;padding:3px 10px;border-radius:99px;background:var(--glass);font-size:.72rem;
font-weight:600;letter-spacing:.04em;text-transform:uppercase;-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px)}
.reel-show{display:flex;align-items:center;gap:8px;font-weight:600;font-size:.9rem}
.reel-show img{width:26px;height:26px;border-radius:6px;object-fit:cover;border:1px solid rgba(255,255,255,.3)}
.reel h2{margin:.55rem 0 .35rem;font:700 1.45rem/1.2 var(--font-display);letter-spacing:-.015em}
.reel p{margin:0;font-size:.95rem;line-height:1.4;color:rgba(255,255,255,.86);display:-webkit-box;-webkit-line-clamp:3;
-webkit-box-orient:vertical;overflow:hidden}
.reel small{display:block;margin-top:.45rem;color:var(--faint);font-size:.8rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.reel-progress{display:flex;align-items:center;gap:10px;margin-top:16px}
.reel-bar{flex:1;height:3px;border-radius:2px;background:rgba(255,255,255,.28);overflow:hidden}
.reel-bar i{display:block;height:100%;width:0;background:#fff}
.reel-time{font-size:.75rem;font-variant-numeric:tabular-nums;color:var(--muted);min-width:42px;text-align:right}
.reel-paused{position:absolute;left:50%;top:45%;width:84px;height:84px;margin:-42px 0 0 -42px;border-radius:50%;
background:rgba(0,0,0,.45);display:grid;place-items:center;opacity:0;transition:opacity .15s;pointer-events:none}
.reel-paused svg{width:44px;height:44px;fill:#fff}
.app.started.paused .reel.on .reel-paused{opacity:1}
.bar{position:absolute;top:0;left:0;right:0;z-index:3;display:flex;align-items:center;gap:10px;padding:14px 14px 0;pointer-events:none}
.bar>*{pointer-events:auto}
.brand{display:flex;align-items:center;gap:10px;border:0;background:none;padding:0;cursor:pointer;text-align:left;
text-shadow:0 1px 3px rgba(0,0,0,.5);min-width:0}
.brand img,.brand .ph{width:38px;height:38px;border-radius:9px;object-fit:cover;flex:none;box-shadow:0 2px 8px rgba(0,0,0,.4)}
.brand b{display:block;font-size:.95rem;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.brand span{display:block;font-size:.78rem;color:var(--muted);line-height:1.2;white-space:nowrap}
.brand>div{min-width:0}
.bar .grow{flex:1}
.btn-round{width:42px;height:42px;border-radius:50%;border:0;display:grid;place-items:center;cursor:pointer;flex:none;
background:var(--glass);color:#fff;-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px)}
.btn-round:hover{background:var(--glass-hover)}.btn-round svg{width:22px;height:22px;fill:currentColor}
.rail{position:absolute;right:14px;bottom:104px;z-index:3;display:flex;flex-direction:column;gap:12px}
.i-play,.app.paused .i-pause{display:none}.app.paused .i-play{display:grid}.i-pause{display:grid}
.nav{display:none}
@media (min-width:700px){.nav{position:absolute;left:calc(100% + 20px);top:50%;transform:translateY(-50%);z-index:3;
display:flex;flex-direction:column;gap:12px}.nav .down svg{transform:rotate(180deg)}}
.ph{background:linear-gradient(135deg,#8a2ecb,#e0477a);display:grid;place-items:center;color:#fff;font-weight:700}
.start{position:absolute;inset:0;z-index:2;display:grid;place-items:center;background:rgba(0,0,0,.35);border:0;cursor:pointer;width:100%}
.start span{display:inline-flex;align-items:center;gap:10px;height:56px;padding:0 26px 0 20px;border-radius:99px;background:#fff;
color:#000;font-weight:700;font-size:1.05rem;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.start svg{width:26px;height:26px;fill:currentColor}
.app.started .start{display:none}
.empty{height:100%;display:grid;place-items:center;text-align:center;padding:32px;color:var(--muted)}
.sheet-back{position:fixed;inset:0;z-index:10;background:rgba(0,0,0,.5);opacity:0;pointer-events:none;transition:opacity .2s}
.sheet{position:fixed;left:0;right:0;bottom:0;z-index:11;max-width:560px;max-height:88vh;max-height:88dvh;margin:0 auto;
overflow-y:auto;overscroll-behavior:contain;background:var(--sheet);border-radius:18px 18px 0 0;padding:10px 20px 32px;
transform:translateY(100%);transition:transform .25s ease;visibility:hidden}
.sheet-open .sheet{transform:none;visibility:visible}.sheet-open .sheet-back{opacity:1;pointer-events:auto}
.grip{width:38px;height:5px;border-radius:3px;background:var(--line);margin:0 auto 14px}
.sheet-close{position:absolute;top:12px;right:12px;width:32px;height:32px;background:var(--sheet-2)}
.sheet-close svg{width:18px;height:18px}
.show{display:flex;gap:16px;align-items:center}
.show img,.show .ph{width:96px;height:96px;border-radius:12px;object-fit:cover;flex:none;font-size:2.4rem}
.kicker{font-size:.7rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--faint)}
.show h1{margin:.1rem 0 .1rem;font:700 1.5rem/1.15 var(--font-display);letter-spacing:-.02em}
.author{color:var(--accent);font-weight:500}
.desc{color:var(--muted);margin:14px 0}
.actions{display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-flex;align-items:center;gap:7px;height:36px;padding:0 16px;border-radius:999px;border:0;background:var(--sheet-2);
color:var(--fg);cursor:pointer;font-size:.9rem;font-weight:600;text-decoration:none}
.btn:hover{background:#3a3a3c}.btn svg{width:17px;height:17px;fill:currentColor;flex:none}
.btn.primary{background:var(--accent);color:#1c1c1e}
.btn .ok,.btn.done .cp{display:none}.btn.done .ok{display:block}
.stats{margin-top:14px}
.sheet h3{font:700 1.1rem/1.2 var(--font-display);margin:26px 0 8px}
.sheet h3 small{font:500 .85rem var(--font);color:var(--faint);margin-left:6px}
.eps{list-style:none;margin:0;padding:0}
.eps li{display:flex;align-items:center;gap:12px;border-top:1px solid var(--line)}
.eps li:first-child{border-top:0}
.eps button{flex:1;min-width:0;display:flex;align-items:center;gap:12px;border:0;background:none;padding:10px 0;cursor:pointer;text-align:left}
.eps .stack{display:flex;padding-left:6px;flex:none}
.eps .stack img,.eps .stack .ph{width:26px;height:26px;border-radius:6px;object-fit:cover;margin-left:-6px;border:2px solid var(--sheet);font-size:.7rem}
.eps b{display:block;font-weight:600}.eps span{display:block;color:var(--faint);font-size:.8rem}
.eps .dl{color:var(--faint);display:grid;place-items:center;width:34px;height:34px;border-radius:50%}
.eps .dl:hover{background:var(--sheet-2);color:#fff}.eps .dl svg{width:20px;height:20px;fill:currentColor}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px 10px}
@media (max-width:420px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
.pod{font-size:.75rem;min-width:0}
.pod .art{width:100%;aspect-ratio:1;border-radius:8px;object-fit:cover;display:block}
.pod .ph.art{display:grid;font-size:1.4rem}
.pod span{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-top:5px;line-height:1.25}
.pod small{display:block;color:var(--faint);font-size:.7rem}
.foot{margin-top:24px;color:var(--faint);font-size:.75rem}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.fallback{height:100%;overflow-y:auto;padding:24px 20px;background:var(--sheet)}
.fallback audio{width:100%;margin:6px 0 18px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

JS = r"""
(function(){
  var ICON={play:'<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>'};
  var app=document.querySelector('.app'),feed=app.querySelector('.feed');
  var data=JSON.parse(document.getElementById('qrated-data').textContent),slides=data.slides,eds={};
  data.editions.forEach(function(e){eds[e.id]=e;});
  if(!slides.length)return;
  function fmt(s){s=Math.max(0,Math.floor(s||0));var h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;
    return (h?h+':'+String(m).padStart(2,'0'):m)+':'+String(x).padStart(2,'0');}
  function esc(t){var d=document.createElement('div');d.textContent=t==null?'':t;return d.innerHTML;}

  feed.innerHTML=slides.map(function(s,i){
    var art=s.art?'<img class="reel-art" src="'+s.art+'" alt="" loading="'+(i<3?'eager':'lazy')+'">':
      '<div class="reel-art ph">'+esc((s.podcast||'?').charAt(0))+'</div>';
    var ed=eds[s.ed],isNew=s.n===0?'<span class="reel-new">'+esc(ed.short)+' &middot; '+ed.stories+(ed.stories===1?' story':' stories')+'</span>':'';
    return '<section class="reel" data-i="'+i+'" aria-label="'+esc(s.title)+'">'+
      '<div class="reel-bg"'+(s.art?' style="background-image:url(\''+s.art+'\')"':'')+'></div><div class="reel-shade"></div>'+
      '<div class="reel-center">'+art+'</div><div class="reel-info">'+isNew+
      '<div class="reel-show">'+(s.art?'<img src="'+s.art+'" alt="">':'')+'<span>'+esc(s.podcast)+'</span></div>'+
      '<h2>'+esc(s.title)+'</h2><p>'+esc(s.summary||'')+'</p><small>'+esc(s.episode||'')+'</small>'+
      '<div class="reel-progress"><div class="reel-bar"><i></i></div><span class="reel-time">'+fmt(s.end-s.start)+'</span></div></div>'+
      '<div class="reel-paused" aria-hidden="true">'+ICON.play+'</div></section>';}).join('');
  var els=[].slice.call(feed.querySelectorAll('.reel')),cur=-1,started=false,advancing=null,audios={},audio=null,pending=null;

  function audioFor(id){if(!audios[id]){var a=new Audio();a.preload='none';a.src=eds[id].file;
      a.addEventListener('timeupdate',function(){if(a===audio)tick();});
      a.addEventListener('loadedmetadata',function(){if(a===audio&&pending!=null){a.currentTime=pending;pending=null;}});
      a.addEventListener('play',sync);a.addEventListener('pause',sync);audios[id]=a;}
    return audios[id];}
  function seek(a,t){if(a.readyState<1){pending=t;a.preload='auto';a.load();}else{pending=null;a.currentTime=t;}}
  function play(){if(!audio)return;var p=audio.play();if(p&&p.catch)p.catch(function(){});}
  function toggle(){if(!started)return start();audio.paused?play():audio.pause();}
  function sync(){app.classList.toggle('paused',!audio||audio.paused);}
  function brand(s){var ed=eds[s.ed];app.querySelector('.brand span').textContent=ed.date+' · '+(s.n+1)+' / '+ed.count;}

  function activate(i){if(i===cur)return;cur=i;advancing=null;var s=slides[i],a=audioFor(s.ed);
    els.forEach(function(el,j){el.classList.toggle('on',j===i);});
    Object.keys(audios).forEach(function(k){if(audios[k]!==a)audios[k].pause();});
    audio=a;seek(a,s.start);brand(s);if(started)play();sync();tick();
    history.replaceState(null,'','#ed-'+s.ed);
    if('mediaSession' in navigator&&window.MediaMetadata){
      navigator.mediaSession.metadata=new MediaMetadata({title:s.title,artist:s.podcast,album:data.title,
        artwork:s.art?[{src:new URL(s.art,location.href).href,sizes:'600x600'}]:[]});}}
  function goTo(i){if(i<0||i>=els.length||advancing===i)return;advancing=i;els[i].scrollIntoView({behavior:'smooth',block:'start'});}
  function tick(){if(cur<0||!audio)return;var s=slides[cur],t=pending!=null?pending:audio.currentTime,
      f=Math.max(0,Math.min(1,(t-s.start)/Math.max(1,s.end-s.start))),el=els[cur];
    el.querySelector('.reel-bar i').style.width=(f*100)+'%';
    el.querySelector('.reel-time').textContent='-'+fmt(Math.max(0,s.end-t));
    if(started&&!audio.paused&&t>=s.end-0.3&&cur<els.length-1)goTo(cur+1);}
  function start(){started=true;app.classList.add('started');play();sync();}

  var obs=new IntersectionObserver(function(es){es.forEach(function(e){
    if(e.isIntersecting&&e.intersectionRatio>=0.6)activate(+e.target.dataset.i);});},{root:feed,threshold:[0.6]});
  els.forEach(function(el){obs.observe(el);el.addEventListener('click',toggle);});

  var first=0,m=location.hash.match(/^#ed-(\d+)$/);
  if(m){for(var i=0;i<slides.length;i++)if(String(slides[i].ed)===m[1]){first=i;break;}}
  feed.scrollTop=els[first].offsetTop;activate(first);

  app.querySelector('.start').addEventListener('click',start);
  app.querySelector('.toggle').addEventListener('click',toggle);
  app.querySelector('.up').addEventListener('click',function(){goTo(cur-1);});
  app.querySelector('.down').addEventListener('click',function(){goTo(cur+1);});
  if('mediaSession' in navigator){var ms=navigator.mediaSession;
    try{ms.setActionHandler('play',function(){started?play():start();});ms.setActionHandler('pause',function(){if(audio)audio.pause();});
      ms.setActionHandler('previoustrack',function(){goTo(cur-1);});ms.setActionHandler('nexttrack',function(){goTo(cur+1);});}catch(_){}}

  // Info sheet: channel, subscribe, episodes, shows in the mix.
  var root=document.documentElement,sheet=document.querySelector('.sheet'),lastFocus=null;
  function openSheet(){lastFocus=document.activeElement;root.classList.add('sheet-open');sheet.setAttribute('aria-hidden','false');
    sheet.querySelector('.sheet-close').focus();}
  function closeSheet(){root.classList.remove('sheet-open');sheet.setAttribute('aria-hidden','true');if(lastFocus)lastFocus.focus();}
  [].slice.call(document.querySelectorAll('.open-sheet')).forEach(function(b){b.addEventListener('click',openSheet);});
  document.querySelector('.sheet-back').addEventListener('click',closeSheet);
  sheet.querySelector('.sheet-close').addEventListener('click',closeSheet);
  [].slice.call(sheet.querySelectorAll('[data-goto]')).forEach(function(b){b.addEventListener('click',function(){
    var id=b.dataset.goto;closeSheet();for(var i=0;i<slides.length;i++)if(String(slides[i].ed)===id){
      feed.scrollTop=els[i].offsetTop;activate(i);if(!started)start();break;}});});
  var copy=sheet.querySelector('.copy');
  if(copy&&navigator.clipboard)copy.addEventListener('click',function(){navigator.clipboard.writeText(copy.dataset.url).then(function(){
    var label=copy.querySelector('span'),t=label.textContent;copy.classList.add('done');label.textContent='Copied';
    setTimeout(function(){copy.classList.remove('done');label.textContent=t;},1500);});});
  else if(copy)copy.hidden=true;

  document.addEventListener('keydown',function(e){if(e.metaKey||e.ctrlKey||e.altKey)return;var k=e.key;
    if(root.classList.contains('sheet-open')){if(k==='Escape'){e.preventDefault();closeSheet();}return;}
    var tag=e.target.tagName;if(tag==='BUTTON'&&(k===' '||k==='Enter'))return;
    if(k==='ArrowDown'||k==='j'||k==='PageDown'){e.preventDefault();goTo(cur+1);}
    else if(k==='ArrowUp'||k==='k'||k==='PageUp'){e.preventDefault();goTo(cur-1);}
    else if(k===' '){e.preventDefault();toggle();}
    else if(k==='i'){openSheet();}});
})();
"""

ICON_PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>'
ICON_PAUSE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5h4v14H6zm8 0h4v14h-4z"/></svg>'
ICON_UP = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7.4 15.4 12 10.8l4.6 4.6L18 14l-6-6-6 6z"/></svg>'
ICON_INFO = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 7h2v2h-2zm0 4h2v6h-2zm1-9a10 10 0 1 0 0 20 10 10 0 0 0 '
             '0-20zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16z"/></svg>')
ICON_CLOSE = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 6.4 17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 '
              '6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z"/></svg>')
ICON_DOWNLOAD = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 4h2v9l3.5-3.5 1.4 1.4L12 16.8 6.1 10.9l1.4-1.4L11 13z'
                 'M5 18h14v2H5z"/></svg>')
ICON_RSS = ('<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="18" r="2.2"/>'
            '<path d="M4 10.5v2.7a6.8 6.8 0 0 1 6.8 6.8h2.7A9.5 9.5 0 0 0 4 10.5zm0-5.3v2.7A12.1 12.1 0 0 1 16.1 20h2.7'
            'A14.8 14.8 0 0 0 4 5.2z"/></svg>')
ICON_COPY = ('<svg class="cp" viewBox="0 0 24 24" aria-hidden="true"><path d="M16 1H4a2 2 0 0 0-2 2v14h2V3h12zm3 4H8'
             'a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H8V7h11z"/></svg>'
             '<svg class="ok" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg>')


def _e(text) -> str:
    return html.escape(str(text if text is not None else ""))


def _cover(file: str | None, name: str = "", cls: str = "art") -> str:
    if file:
        return f'<img class="{cls}" src="covers/{_e(file)}" alt="{_e(name)}" title="{_e(name)}" loading="lazy">'
    return f'<div class="ph {cls}" title="{_e(name)}" aria-hidden="true">{_e((name or "?")[:1].upper())}</div>'


def _json_script(data, element_id: str) -> str:
    """Embed JSON safely inside a <script> element."""
    text = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/json" id="{element_id}">{text}</script>'


def _chapters(ed: sqlite3.Row, items: list[sqlite3.Row], feed_title: str, art: str | None = None) -> list[dict]:
    """Opening, one chapter per story, closing; empty for editions built before chapters existed."""
    timed = [it for it in items if it["chapter_start"] is not None and it["chapter_end"] is not None]
    if not timed or len(timed) != len(items):
        return []
    duration = ed["duration"] or timed[-1]["chapter_end"]
    chapters = [{"start": 0.0, "end": timed[0]["chapter_start"], "kind": "intro",
                 "title": "Welcome to today's selection", "podcast": feed_title, "art": art}]
    for it in timed:
        chapters.append({
            "start": it["chapter_start"], "end": it["chapter_end"], "kind": "item", "title": it["title"],
            "podcast": it["podcast"], "summary": it["summary"], "episode": it["episode_title"],
            "art": f"covers/{it['image_file']}" if it["image_file"] else None,
        })
    chapters.append({"start": timed[-1]["chapter_end"], "end": duration, "kind": "outro",
                     "title": "That's it for today", "podcast": feed_title, "art": art})
    return chapters


def _edition_items(conn: sqlite3.Connection, edition_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT i.*, e.podcast, e.title AS episode_title, f.image_file FROM items i"
        " JOIN episodes e ON e.guid = i.episode_guid"
        " LEFT JOIN feeds f ON f.url = e.feed_url"
        " WHERE i.edition_id=? ORDER BY i.position",
        (edition_id,),
    ).fetchall()


def build_feed_data(conn: sqlite3.Connection, cfg: Config) -> dict:
    """Slides (one per story, newest edition first) and edition metadata for the page script."""
    tz = ZoneInfo(cfg.tz)
    art = cover_url(cfg)
    slides, editions = [], []
    for ed in conn.execute("SELECT * FROM editions ORDER BY id DESC").fetchall():
        items = _edition_items(conn, ed["id"])
        created = datetime.fromisoformat(ed["created_at"]).astimezone(tz)
        duration = ed["duration"] or 0
        stories = [c for c in _chapters(ed, items, cfg.feed_title, art) if c["kind"] == "item"]
        if not stories:  # built before chapter data existed: the whole edition as one slide
            stories = [{
                "start": 0.0, "end": duration, "title": f"{len(items)} stories in one episode",
                "podcast": cfg.feed_title, "art": art, "episode": "Full episode",
                "summary": " · ".join(it["title"] for it in items),
            }]
        for n, s in enumerate(stories):
            slides.append({
                "ed": ed["id"], "n": n, "start": s["start"], "end": s["end"], "title": s["title"],
                "podcast": s["podcast"], "summary": s.get("summary") or "", "episode": s.get("episode") or "",
                "art": s["art"],
            })
        editions.append({
            "id": ed["id"], "file": f"editions/{ed['file_name']}", "date": f"{created:%a %b} {created.day}",
            "short": f"{created:%b} {created.day}", "long": spoken_date(created), "medium": f"{created:%A, %b} {created.day}", "duration": duration,
            "count": len(stories), "stories": len(items), "items": items,
        })
    return {"title": cfg.feed_title, "slides": slides, "editions": editions}


def render_index(conn: sqlite3.Connection, cfg: Config) -> str:
    tz = ZoneInfo(cfg.tz)
    art = cover_url(cfg)
    description = render(cfg.feed_description, name=cfg.listener_name, title=cfg.feed_title)
    feed = build_feed_data(conn, cfg)
    editions = feed["editions"]
    feed_url = f"{cfg.public_base_url}/feed.xml"
    logo = (f'<img src="{_e(art)}" alt="">' if art else f'<div class="ph">{_e(cfg.feed_title[:1])}</div>')

    # episode list in the info sheet
    ep_rows, fallback = [], []
    for ed in editions:
        items = ed["items"]
        stack, seen = [], set()
        for it in items:
            if it["podcast"] not in seen:
                seen.add(it["podcast"])
                if len(stack) < 5:
                    stack.append(_cover(it["image_file"], it["podcast"], cls=""))
        mins = max(1, round(ed["duration"] / 60))
        ep_rows.append(
            f'<li><button type="button" data-goto="{ed["id"]}"><span class="stack">{"".join(stack)}</span>'
            f'<div><b>{_e(ed["medium"])}</b><span>{len(items)} stories from {len(seen)} shows &middot; {mins} min</span></div>'
            f'</button><a class="dl" href="{_e(ed["file"])}" download aria-label="Download MP3 of {_e(ed["long"])}"'
            f' title="Download MP3">{ICON_DOWNLOAD}</a></li>'
        )
        stories = "".join(
            f'<li><b>{_e(it["title"])}</b> &mdash; {_e(it["podcast"])}'
            + (f' ({mmss(it["chapter_start"])})' if it["chapter_start"] is not None else "")
            + f'<br>{_e(it["summary"])}</li>'
            for it in items
        )
        fallback.append(f'<h3>{_e(ed["long"])}</h3><audio controls preload="none" src="{_e(ed["file"])}"></audio>'
                        f"<ol>{stories}</ol>")

    pods = conn.execute(
        "SELECT f.name, f.url, f.image_file,"
        " (SELECT COUNT(*) FROM items i JOIN episodes e ON e.guid=i.episode_guid"
        "  WHERE e.feed_url=f.url AND i.status='used') AS used_items"
        " FROM feeds f ORDER BY LOWER(COALESCE(f.name, f.url))"
    ).fetchall()
    inventory = "".join(
        f'<div class="pod">{_cover(p["image_file"], p["name"] or p["url"])}<span>{_e(p["name"] or p["url"])}</span>'
        + (f'<small>{p["used_items"]} featured</small>' if p["used_items"] else "")
        + "</div>"
        for p in pods
    )
    total_stories = sum(len(ed["items"]) for ed in editions)
    stats = " &middot; ".join(
        ["Daily", f'{len(editions)} episode{"" if len(editions) == 1 else "s"}', f"{total_stories} stories",
         f"{len(pods)} shows"]
    )

    script_data = {
        "title": feed["title"], "slides": feed["slides"],
        "editions": [{k: v for k, v in ed.items() if k != "items"} for ed in editions],
    }
    if editions:
        stage = (
            '<div class="feed" role="feed" aria-label="Stories"></div>'
            '<button class="start" type="button" aria-label="Start listening">'
            f"<span>{ICON_PLAY}Listen</span></button>"
            '<div class="rail"><button class="btn-round toggle" type="button" aria-label="Play or pause">'
            f'<span class="i-pause">{ICON_PAUSE}</span><span class="i-play">{ICON_PLAY}</span></button>'
            f'<button class="btn-round open-sheet" type="button" aria-label="About this podcast">{ICON_INFO}</button></div>'
            '<div class="nav"><button class="btn-round up" type="button" aria-label="Previous story">'
            f'{ICON_UP}</button><button class="btn-round down" type="button" aria-label="Next story">{ICON_UP}</button></div>'
        )
    else:
        stage = '<div class="empty">No episodes yet. The first one appears after the next run.</div>'

    sheet = (
        '<div class="sheet-back"></div>'
        '<div class="sheet" role="dialog" aria-modal="true" aria-label="About this podcast" aria-hidden="true">'
        f'<div class="grip"></div><button class="btn-round sheet-close" type="button" aria-label="Close">{ICON_CLOSE}</button>'
        f'<div class="show">{logo}<div><div class="kicker">Podcast</div><h1>{_e(cfg.feed_title)}</h1>'
        f'<div class="author">Curated for {_e(cfg.listener_name)}</div></div></div>'
        f'<p class="desc">{_e(description)}</p>'
        f'<div class="actions"><a class="btn primary" href="feed.xml">{ICON_RSS}<span>Subscribe</span></a>'
        f'<button class="btn copy" type="button" data-url="{_e(feed_url)}">{ICON_COPY}<span>Copy feed URL</span></button></div>'
        f'<div class="kicker stats">{stats}</div>'
        f'<h3>Episodes <small>{len(editions)}</small></h3><ul class="eps">{"".join(ep_rows)}</ul>'
        f'<h3>Shows in the mix <small>{len(pods)}</small></h3><div class="grid">{inventory}</div>'
        f'<div class="foot">Updated {datetime.now(tz):%Y-%m-%d %H:%M} &middot; Swipe or use &uarr;/&darr; to move between '
        "stories, tap or press space to pause, i for this panel.</div></div>"
    )

    head = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="theme-color" content="#000000">'
        f"<title>{_e(cfg.feed_title)}</title>"
        f'<meta name="description" content="{_e(description)}">'
        f'<meta property="og:title" content="{_e(cfg.feed_title)}">'
        f'<meta property="og:description" content="{_e(description)}">'
        + (f'<meta property="og:image" content="{_e(cover_url(cfg, absolute=True))}">'
           f'<link rel="icon" href="{_e(art)}"><link rel="apple-touch-icon" href="{_e(art)}">' if art else "")
        + f'<link rel="alternate" type="application/rss+xml" title="{_e(cfg.feed_title)}" href="feed.xml">'
        f"<style>{CSS}</style></head><body>"
    )
    return (
        head
        + '<main class="app paused">'
        f'<h1 class="sr">{_e(cfg.feed_title)}</h1>'
        '<div class="bar"><button class="brand open-sheet" type="button" aria-label="About this podcast">'
        f'{logo}<div><b>{_e(cfg.feed_title)}</b><span></span></div></button></div>'
        f"{stage}</main>{sheet}"
        f'<noscript><div class="fallback"><h1>{_e(cfg.feed_title)}</h1><p>{_e(description)}</p>'
        f'<p><a href="feed.xml">Subscribe via RSS</a></p>{"".join(fallback)}</div>'
        "<style>.app{display:none}</style></noscript>"
        f'{_json_script(script_data, "qrated-data")}<script>{JS}</script></body></html>'
    )


def write_index(conn: sqlite3.Connection, cfg: Config) -> str:
    """Write public/index.html and return its path."""
    cfg.public_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.public_dir / "index.html"
    path.write_text(render_index(conn, cfg), encoding="utf-8")
    return str(path)
