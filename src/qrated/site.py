"""Static HTML homepage: channel header, editions with a chapter-aware player, and podcast inventory."""

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
:root{--bg:#f6f5f1;--fg:#1b1b1f;--muted:#6a6a72;--card:#fff;--line:#e4e2da;--soft:#eeece5;
--accent:#5a47e0;--accent-2:#e0477a;--on-accent:#fff;--shadow:0 1px 2px rgba(0,0,0,.05),0 8px 24px rgba(0,0,0,.06)}
@media (prefers-color-scheme:dark){:root{--bg:#121215;--fg:#ececf0;--muted:#9b9ba6;--card:#1c1c21;--line:#2c2c33;
--soft:#25252c;--accent:#9d8cff;--accent-2:#ff7aa8;--on-accent:#121215;--shadow:0 1px 2px rgba(0,0,0,.4)}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:32px 16px 72px}
a{color:var(--accent)}button{font:inherit;color:inherit}
.hero{display:flex;gap:20px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.logo img{width:100%;height:100%;border-radius:inherit;object-fit:cover;display:block}
.logo{width:88px;height:88px;border-radius:22px;flex:none;display:grid;place-items:center;color:#fff;
font:800 44px/1 ui-sans-serif,system-ui,sans-serif;background:linear-gradient(135deg,#5a47e0,#e0477a);box-shadow:var(--shadow)}
.hero h1{margin:0;font-size:2.2rem;letter-spacing:-.02em;line-height:1.1}
.hero p{margin:.3rem 0 .8rem;color:var(--muted)}
.actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.btn{display:inline-flex;align-items:center;gap:6px;padding:.45rem 1rem;border-radius:999px;border:1px solid var(--line);
background:var(--card);text-decoration:none;color:var(--fg);cursor:pointer;font-size:.92rem}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}
.stats{color:var(--muted);font-size:.9rem;margin-top:.6rem}
h2{font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:2.5rem 0 .9rem}
.editions{display:flex;flex-direction:column;gap:12px}
.edition{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);overflow:clip}
.edition[open]{border-color:color-mix(in srgb,var(--accent) 45%,var(--line))}
.edition>summary{list-style:none;display:flex;gap:14px;align-items:center;padding:14px 16px;cursor:pointer}
.edition>summary::-webkit-details-marker{display:none}
.edition>summary:hover{background:var(--soft)}
.edition>summary:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.sum-main{flex:1;min-width:0}
.sum-main b{font-size:1.1rem}.sum-main small{display:block;color:var(--muted)}
.pill{display:inline-block;vertical-align:2px;margin-left:8px;font-size:.7rem;font-weight:600;padding:1px 8px;border-radius:99px;
background:var(--accent);color:var(--on-accent);text-transform:uppercase;letter-spacing:.05em}
.chev{flex:none;width:32px;height:32px;border-radius:50%;display:grid;place-items:center;color:var(--muted);transition:transform .2s}
.chev svg{width:20px;height:20px;fill:currentColor}.edition[open] .chev{transform:rotate(180deg)}
.stack{display:flex;margin-top:8px;padding-left:6px}
.stack img,.stack .ph{width:32px;height:32px;border-radius:50%;object-fit:cover;margin-left:-6px;border:2px solid var(--card);font-size:.8rem}
.edition-body{border-top:1px solid var(--line)}
.ph{background:var(--soft);display:grid;place-items:center;color:var(--muted);font-weight:700}
.ph.q{background:linear-gradient(135deg,#5a47e0,#e0477a);color:#fff}
.muted{color:var(--muted)}
.fallback-audio{width:100%;padding:12px 16px}
.player{display:none;position:sticky;top:0;z-index:2;background:var(--card);padding:14px 16px 12px;border-bottom:1px solid var(--line)}
.now{display:flex;gap:12px;align-items:center;min-height:60px}
.now .art{width:60px;height:60px;border-radius:10px;object-fit:cover;flex:none}
.now small{display:block;color:var(--accent);font-weight:600;font-size:.75rem;text-transform:uppercase;letter-spacing:.06em}
.now b{display:block;line-height:1.25;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.now span{color:var(--muted);font-size:.88rem}
.timeline{position:relative;margin:26px 0 6px;height:28px;cursor:pointer;touch-action:none;outline:none}
.marks{position:absolute;left:0;right:0;top:-24px;height:22px}
.marks img,.marks .ph{position:absolute;width:22px;height:22px;border-radius:50%;object-fit:cover;transform:translateX(-2px);
border:2px solid var(--card);font-size:9px;cursor:pointer;transition:transform .12s}
.marks img:hover,.marks .ph:hover,.marks .on{transform:translateX(-2px) scale(1.35);z-index:1;border-color:var(--accent)}
.bar{position:absolute;left:0;right:0;top:9px;height:10px;border-radius:99px;background:var(--soft);overflow:hidden}
.seg{position:absolute;top:0;bottom:0;border-left:2px solid var(--card);background:var(--line);transition:background .15s}
.seg.k-item:nth-child(odd){background:color-mix(in srgb,var(--accent) 45%,var(--soft))}
.seg.k-item:nth-child(even){background:color-mix(in srgb,var(--accent-2) 45%,var(--soft))}
.seg.hot{background:var(--fg)!important;opacity:.55}
.fill{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg,var(--accent),var(--accent-2));width:0;opacity:.9}
.head{position:absolute;top:6px;z-index:1;width:16px;height:16px;border-radius:50%;background:var(--fg);transform:translateX(-8px);
box-shadow:0 0 0 3px var(--card);left:0;transition:transform .1s}
.timeline:focus-visible .head,.timeline:hover .head{transform:translateX(-8px) scale(1.15)}
.ghost{position:absolute;top:6px;bottom:6px;width:2px;background:var(--fg);opacity:0;pointer-events:none}
.tip{position:absolute;bottom:40px;left:0;width:250px;display:flex;gap:10px;padding:10px;border-radius:12px;background:var(--fg);
color:var(--bg);box-shadow:var(--shadow);opacity:0;pointer-events:none;transform:translateY(4px);transition:opacity .12s,transform .12s;z-index:3}
.tip.on{opacity:1;transform:none}.timeline.hovering .ghost{opacity:.35}
.tip img,.tip .ph{width:52px;height:52px;border-radius:8px;object-fit:cover;flex:none}
.tip b{display:block;font-size:.88rem;line-height:1.25;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tip span{display:block;font-size:.78rem;opacity:.75;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tip>div{min-width:0}.tip small{font-size:.75rem;opacity:.6;font-variant-numeric:tabular-nums}
.controls{display:flex;align-items:center;gap:6px}
.ctl{width:36px;height:36px;border-radius:50%;border:0;background:transparent;cursor:pointer;display:grid;place-items:center}
.ctl:hover{background:var(--soft)}.ctl svg{width:20px;height:20px;fill:currentColor}
.ctl.play{width:46px;height:46px;background:var(--accent);color:var(--on-accent)}.ctl.play:hover{background:var(--accent);filter:brightness(1.1)}
.ctl.play svg{width:22px;height:22px}
.time{font-variant-numeric:tabular-nums;color:var(--muted);font-size:.85rem;margin-left:6px}
.dl{color:var(--muted)}.dl:hover{color:var(--fg)}
.speed{margin-left:auto;border:1px solid var(--line);background:transparent;border-radius:99px;padding:.2rem .6rem;cursor:pointer;font-size:.8rem;font-variant-numeric:tabular-nums}
.stories{list-style:none;margin:0;padding:6px 8px 10px}
.item{display:flex;gap:12px;padding:10px;border-radius:12px;align-items:flex-start}
.item.has-t{cursor:pointer}.item.has-t:hover{background:var(--soft)}
.item.playing{background:color-mix(in srgb,var(--accent) 12%,transparent)}
.item .art{width:56px;height:56px;border-radius:10px;object-fit:cover;flex:none}
.item .meta{color:var(--muted);font-size:.86rem}.item p{margin:.25rem 0 0;font-size:.95rem}
.item .at{font-variant-numeric:tabular-nums;font-size:.78rem;color:var(--accent);font-weight:600;margin-left:auto;padding-left:8px;flex:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:16px}
.pod{text-align:center;font-size:.85rem;text-decoration:none;color:inherit}
.pod .art{width:100%;aspect-ratio:1;border-radius:14px;object-fit:cover;display:block;box-shadow:var(--shadow);font-size:1.6rem}
.pod span{display:block;margin-top:6px;line-height:1.25}
.badge{display:inline-block;margin-top:3px;font-size:.72rem;padding:1px 7px;border-radius:99px;background:var(--soft);color:var(--muted)}
.empty{padding:28px;text-align:center;background:var(--card);border:1px dashed var(--line);border-radius:14px;color:var(--muted)}
footer{margin-top:3rem;color:var(--muted);font-size:.82rem}
.js .player{display:block}.js .fallback-audio{display:none}
@media (prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
"""

JS = r"""
(function(){
  var root=document.documentElement;root.classList.add('js');
  var ICON={play:'<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>',
    pause:'<svg viewBox="0 0 24 24"><path d="M6 5h4v14H6zm8 0h4v14h-4z"/></svg>'};
  function fmt(s){s=Math.max(0,Math.floor(s||0));var h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;
    return (h?h+':'+String(m).padStart(2,'0'):m)+':'+String(x).padStart(2,'0');}
  function artHtml(c,cls){return c.art?'<img class="'+cls+'" src="'+c.art+'" alt="">':
    '<div class="ph '+cls+(c.kind!=='item'?' q':'')+'">'+(c.kind!=='item'?'Q':(c.podcast||'?').charAt(0))+'</div>';}
  function esc(t){var d=document.createElement('div');d.textContent=t==null?'':t;return d.innerHTML;}

  function Player(sec){
    var data=JSON.parse(sec.querySelector('script[type="application/json"]').textContent);
    var audio=sec.querySelector('audio'),el=sec.querySelector('.player'),tl=el.querySelector('.timeline'),
      fill=el.querySelector('.fill'),head=el.querySelector('.head'),ghost=el.querySelector('.ghost'),tip=el.querySelector('.tip'),
      playBtn=el.querySelector('.play'),time=el.querySelector('.time'),speed=el.querySelector('.speed'),
      now=el.querySelector('.now'),segs=[].slice.call(el.querySelectorAll('.seg')),marks=[].slice.call(el.querySelectorAll('.marks [data-chapter]')),
      rows=[].slice.call(sec.querySelectorAll('.stories .item')),chapters=data.chapters,dur=data.duration||0,cur=-2,dragging=false,pending=null;
    function total(){return isFinite(audio.duration)&&audio.duration>0?audio.duration:dur;}
    function chapterAt(t){for(var i=chapters.length-1;i>=0;i--)if(t>=chapters[i].start)return i;return -1;}
    function setNow(i){if(i===cur)return;cur=i;var c=chapters[i]||{title:data.title,kind:'intro'};
      now.innerHTML=artHtml(c,'art')+'<div><small>'+esc(c.kicker||'Now playing')+'</small><b>'+esc(c.title)+'</b>'+
        '<span>'+esc(c.sub||'')+'</span></div>';
      segs.forEach(function(s,j){s.classList.toggle('hot',j===i);});
      rows.forEach(function(r){r.classList.toggle('playing',!!chapters[i]&&r.dataset.chapter!=null&&+r.dataset.chapter===i);});
      if('mediaSession' in navigator&&window.MediaMetadata){var art=c.art?[{src:new URL(c.art,location.href).href,sizes:'512x512'}]:[];
        navigator.mediaSession.metadata=new MediaMetadata({title:c.title,artist:c.sub||data.title,album:data.title,artwork:art});}}
    function render(at){var t=typeof at==='number'?at:(pending!=null?pending:audio.currentTime),T=total(),p=T?Math.min(1,t/T):0;
      fill.style.width=(p*100)+'%';head.style.left=(p*100)+'%';time.textContent=fmt(t)+' / '+fmt(T);
      tl.setAttribute('aria-valuenow',Math.round(t));tl.setAttribute('aria-valuetext',fmt(t));
      if(chapters.length)setNow(chapterAt(t));}
    function seek(t){t=Math.max(0,Math.min(total()-0.1,t));
      if(audio.readyState<1){pending=t;audio.preload='auto';audio.load();}else audio.currentTime=t;render(t);}
    function play(){pauseOthers(audio);setActive(api);var p=audio.play();if(p&&p.catch)p.catch(function(){});}
    function toggle(){audio.paused?play():audio.pause();}
    function jump(d){if(!chapters.length)return seek(audio.currentTime+d*30);var i=chapterAt(audio.currentTime);
      if(d<0&&i>=0&&audio.currentTime-chapters[i].start>3)return seek(chapters[i].start);
      var n=Math.max(0,Math.min(chapters.length-1,i+d));seek(chapters[n].start);}
    function xToTime(x){var r=tl.getBoundingClientRect();return Math.max(0,Math.min(1,(x-r.left)/r.width))*total();}
    function showTip(x,forced){var r=tl.getBoundingClientRect(),t=forced!=null?chapters[forced].start:xToTime(x),
      i=forced!=null?forced:chapterAt(t),c=chapters[i],pos=x-r.left;
      ghost.style.left=pos+'px';tl.classList.add('hovering');
      if(c){tip.innerHTML=artHtml(c,'')+'<div><b>'+esc(c.title)+'</b><span>'+esc(c.sub||'')+'</span><small>'+fmt(t)+
        ' &middot; '+fmt(c.start)+'&ndash;'+fmt(c.end)+'</small></div>';}
      else tip.innerHTML='<div><b>'+fmt(t)+'</b></div>';
      var w=tip.offsetWidth;tip.style.left=Math.max(0,Math.min(r.width-w,pos-w/2))+'px';tip.classList.add('on');
      segs.forEach(function(s,j){s.classList.toggle('hot',j===i);});
      marks.forEach(function(m){m.classList.toggle('on',+m.dataset.chapter===i);});}
    function hideTip(){marks.forEach(function(m){m.classList.remove('on');});tip.classList.remove('on');tl.classList.remove('hovering');var i=cur;cur=-2;setNow(i);}

    playBtn.addEventListener('click',toggle);
    el.querySelector('.prev').addEventListener('click',function(){jump(-1);});
    el.querySelector('.next').addEventListener('click',function(){jump(1);});
    var rates=[1,1.25,1.5,1.75,2,0.75];
    speed.addEventListener('click',function(){var i=(rates.indexOf(audio.playbackRate)+1)%rates.length;
      audio.playbackRate=rates[i];speed.textContent=rates[i]+'×';});
    tl.addEventListener('pointermove',function(e){if(e.pointerType==='mouse'||dragging)showTip(e.clientX);if(dragging)seek(xToTime(e.clientX));});
    tl.addEventListener('pointerleave',function(){if(!dragging)hideTip();});
    tl.addEventListener('pointerdown',function(e){dragging=true;tl.setPointerCapture(e.pointerId);showTip(e.clientX);seek(xToTime(e.clientX));});
    tl.addEventListener('pointerup',function(e){dragging=false;tl.releasePointerCapture(e.pointerId);
      if(e.pointerType!=='mouse')hideTip();if(audio.paused)play();});
    tl.addEventListener('keydown',function(e){var k=e.key;
      if(k==='ArrowRight'||k==='ArrowLeft'){e.preventDefault();e.shiftKey?jump(k==='ArrowRight'?1:-1):seek(audio.currentTime+(k==='ArrowRight'?10:-10));}
      else if(k==='Home'){e.preventDefault();seek(0);}else if(k==='End'){e.preventDefault();seek(total());}});
    marks.forEach(function(m){var i=+m.dataset.chapter;
      m.addEventListener('pointerenter',function(){var b=m.getBoundingClientRect();showTip(b.left+b.width/2,i);});
      m.addEventListener('pointerleave',hideTip);
      m.addEventListener('pointerdown',function(e){e.stopPropagation();});
      m.addEventListener('click',function(e){e.stopPropagation();seek(chapters[i].start);play();});});
    rows.forEach(function(r){if(r.dataset.chapter==null)return;r.addEventListener('click',function(){
      seek(chapters[+r.dataset.chapter].start);play();});});
    audio.addEventListener('timeupdate',render);audio.addEventListener('loadedmetadata',function(){if(pending!=null){audio.currentTime=pending;pending=null;}render();});
    audio.addEventListener('play',function(){playBtn.innerHTML=ICON.pause;playBtn.setAttribute('aria-label','Pause');});
    audio.addEventListener('pause',function(){playBtn.innerHTML=ICON.play;playBtn.setAttribute('aria-label','Play');});
    audio.addEventListener('ended',function(){audio.pause();});
    render();if(cur===-2)setNow(-1);
    var api={audio:audio,toggle:toggle,jump:jump,seek:seek,
      activate:function(){if('mediaSession' in navigator){var ms=navigator.mediaSession;
        try{ms.setActionHandler('play',play);ms.setActionHandler('pause',function(){audio.pause();});
          ms.setActionHandler('previoustrack',function(){jump(-1);});ms.setActionHandler('nexttrack',function(){jump(1);});
          ms.setActionHandler('seekto',function(d){seek(d.seekTime);});}catch(_){}}}};
    return api;
  }

  var players={},active=null;
  function pauseOthers(a){Object.keys(players).forEach(function(k){if(players[k].audio!==a)players[k].audio.pause();});}
  function setActive(p){if(p&&p!==active){active=p;p.activate();}}
  var editions=[].slice.call(document.querySelectorAll('details.edition'));
  editions.forEach(function(d){var p=players[d.dataset.id]=Player(d);
    var byUser=false;d.querySelector('summary').addEventListener('click',function(){byUser=true;});
    d.addEventListener('toggle',function(){if(d.open){setActive(p);if(byUser)history.replaceState(null,'','#'+d.id);}
      else p.audio.pause();byUser=false;});});
  function openFromHash(){var d=document.getElementById(location.hash.slice(1));
    if(d&&d.matches('details.edition')){d.open=true;setActive(players[d.dataset.id]);d.scrollIntoView({block:'start'});}}
  if(location.hash)openFromHash();
  else{var first=editions.filter(function(d){return d.open;})[0];if(first)setActive(players[first.dataset.id]);}
  window.addEventListener('hashchange',openFromHash);

  document.addEventListener('keydown',function(e){if(!active||e.metaKey||e.ctrlKey||e.altKey)return;
    var t=e.target.tagName;if(t==='INPUT'||t==='TEXTAREA'||t==='BUTTON'||t==='A'||t==='SUMMARY'||e.target.getAttribute('role')==='slider')return;
    if(e.key===' '||e.key==='k'){e.preventDefault();active.toggle();}
    else if(e.key==='j')active.seek(active.audio.currentTime-15);else if(e.key==='l')active.seek(active.audio.currentTime+15);
    else if(e.key==='n')active.jump(1);else if(e.key==='p')active.jump(-1);});

  var copy=document.querySelector('.copy');
  if(copy&&navigator.clipboard)copy.addEventListener('click',function(){navigator.clipboard.writeText(copy.dataset.url).then(function(){
    var t=copy.textContent;copy.textContent='Copied';setTimeout(function(){copy.textContent=t;},1500);});});
  else if(copy)copy.hidden=true;
})();
"""

ICON_PLAY = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>'
ICON_PREV = '<svg viewBox="0 0 24 24"><path d="M6 6h2v12H6zm3.5 6 8.5 6V6z"/></svg>'
ICON_DOWNLOAD = '<svg viewBox="0 0 24 24"><path d="M11 4h2v9l3.5-3.5 1.4 1.4L12 16.8 6.1 10.9l1.4-1.4L11 13zM5 18h14v2H5z"/></svg>'
ICON_CHEVRON = '<svg viewBox="0 0 24 24"><path d="M7.4 8.6 12 13.2l4.6-4.6L18 10l-6 6-6-6z"/></svg>'
ICON_NEXT = '<svg viewBox="0 0 24 24"><path d="M6 18l8.5-6L6 6zm10-12h2v12h-2z"/></svg>'


def _e(text) -> str:
    return html.escape(str(text if text is not None else ""))


def _cover(file: str | None, name: str = "", cls: str = "art") -> str:
    if file:
        return f'<img class="{cls}" src="covers/{_e(file)}" alt="{_e(name)}" title="{_e(name)}" loading="lazy">'
    return f'<div class="ph {cls}" title="{_e(name)}" aria-hidden="true">{_e((name or "?")[:1].upper())}</div>'


def _json_script(data) -> str:
    """Embed JSON safely inside a <script> element."""
    text = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/json">{text}</script>'


def _chapters(ed: sqlite3.Row, items: list[sqlite3.Row], feed_title: str, art: str | None = None) -> list[dict]:
    """Opening, one chapter per story, closing; empty for editions built before chapters existed."""
    timed = [it for it in items if it["chapter_start"] is not None and it["chapter_end"] is not None]
    if not timed or len(timed) != len(items):
        return []
    duration = ed["duration"] or timed[-1]["chapter_end"]
    chapters = [{"start": 0.0, "end": timed[0]["chapter_start"], "kind": "intro", "kicker": "Opening",
                 "title": "Welcome to today's selection", "sub": feed_title, "art": art}]
    for n, it in enumerate(timed, start=1):
        chapters.append({
            "start": it["chapter_start"], "end": it["chapter_end"], "kind": "item",
            "kicker": f"Story {n} of {len(timed)}", "title": it["title"],
            "sub": f"{it['podcast']} · {it['episode_title'] or ''}".rstrip(" ·"),
            "podcast": it["podcast"],
            "art": f"covers/{it['image_file']}" if it["image_file"] else None,
        })
    chapters.append({"start": timed[-1]["chapter_end"], "end": duration, "kind": "outro", "kicker": "Closing",
                     "title": "That's it for today", "sub": feed_title, "art": art})
    return chapters


def _player(chapters: list[dict], duration: float, file_name: str) -> str:
    segs, marks = [], []
    for i, c in enumerate(chapters):
        left = 100 * c["start"] / duration if duration else 0
        width = 100 * max(c["end"] - c["start"], 0) / duration if duration else 0
        segs.append(f'<div class="seg k-{c["kind"]}" style="left:{left:.3f}%;width:{width:.3f}%"></div>')
        if c["kind"] == "item":
            pos = f'data-chapter="{i}" style="left:{left:.3f}%"'
            art = (f'<img src="{_e(c["art"])}" alt="{_e(c["podcast"])}" {pos}>' if c["art"]
                   else f'<div class="ph" {pos}>{_e(c["podcast"][:1].upper())}</div>')
            marks.append(art)
    return (
        '<div class="player"><div class="now"></div>'
        f'<div class="timeline" role="slider" tabindex="0" aria-label="Seek" aria-valuemin="0"'
        f' aria-valuemax="{int(duration)}"><div class="marks">{"".join(marks)}</div>'
        f'<div class="bar">{"".join(segs)}<div class="fill"></div></div>'
        '<div class="ghost"></div><div class="head"></div><div class="tip" aria-hidden="true"></div></div>'
        '<div class="controls">'
        f'<button class="ctl prev" aria-label="Previous story">{ICON_PREV}</button>'
        f'<button class="ctl play" aria-label="Play">{ICON_PLAY}</button>'
        f'<button class="ctl next" aria-label="Next story">{ICON_NEXT}</button>'
        '<span class="time">0:00</span><button class="speed" aria-label="Playback speed">1×</button>'
        f'<a class="ctl dl" href="editions/{_e(file_name)}" download aria-label="Download MP3"'
        f' title="Download MP3">{ICON_DOWNLOAD}</a>'
        "</div></div>"
    )


def render_index(conn: sqlite3.Connection, cfg: Config) -> str:
    tz = ZoneInfo(cfg.tz)
    editions = conn.execute("SELECT * FROM editions ORDER BY id DESC").fetchall()

    art = cover_url(cfg)
    description = render(cfg.feed_description, name=cfg.listener_name, title=cfg.feed_title)
    cards, total_stories = [], 0
    for idx, ed in enumerate(editions):
        items = conn.execute(
            "SELECT i.*, e.podcast, e.title AS episode_title, f.image_file FROM items i"
            " JOIN episodes e ON e.guid = i.episode_guid"
            " LEFT JOIN feeds f ON f.url = e.feed_url"
            " WHERE i.edition_id=? ORDER BY i.position",
            (ed["id"],),
        ).fetchall()
        total_stories += len(items)
        created = datetime.fromisoformat(ed["created_at"]).astimezone(tz)
        duration = ed["duration"] or 0
        mins = max(1, round(duration / 60))
        chapters = _chapters(ed, items, cfg.feed_title, art)

        stack, seen = [], set()
        for it in items:
            if it["podcast"] not in seen:
                seen.add(it["podcast"])
                if len(stack) < 10:
                    stack.append(_cover(it["image_file"], it["podcast"], cls=""))
        latest = '<span class="pill">Latest</span>' if idx == 0 else ""
        summary = (
            f'<summary><div class="sum-main"><b>{_e(spoken_date(created))}</b>{latest}'
            f'<small>{created:%H:%M} &middot; {len(items)} stories from {len(seen)} shows &middot; {mins} min</small>'
            f'<span class="stack">{"".join(stack)}</span></div>'
            f'<span class="chev" aria-hidden="true">{ICON_CHEVRON}</span></summary>'
        )

        rows = []
        for n, it in enumerate(items):
            chapter = n + 1 if chapters else None  # chapter 0 is the opening
            attr = f' data-chapter="{chapter}"' if chapter is not None else ""
            at = f'<span class="at">{mmss(it["chapter_start"])}</span>' if chapter is not None else ""
            rows.append(
                f'<li class="item{" has-t" if chapter is not None else ""}"{attr}>'
                f'{_cover(it["image_file"], it["podcast"])}<div><b>{_e(it["title"])}</b>'
                f'<div class="meta">{_e(it["podcast"])} &middot; {_e(it["episode_title"])}'
                f' ({mmss(it["start_sec"])}&ndash;{mmss(it["end_sec"])})</div>'
                f'<p>{_e(it["summary"])}</p></div>{at}</li>'
            )
        data = {"title": ed["title"], "duration": duration, "chapters": chapters}
        cards.append(
            f'<details class="edition" id="ed-{ed["id"]}" data-id="{ed["id"]}"{" open" if idx == 0 else ""}>'
            f'{summary}<div class="edition-body">{_player(chapters, duration, ed["file_name"])}'
            f'<audio class="fallback-audio" controls preload="metadata" src="editions/{_e(ed["file_name"])}"></audio>'
            f'<ol class="stories">{"".join(rows)}</ol></div>{_json_script(data)}</details>'
        )

    pods = conn.execute(
        "SELECT f.name, f.url, f.image_file,"
        " (SELECT COUNT(*) FROM items i JOIN episodes e ON e.guid=i.episode_guid"
        "  WHERE e.feed_url=f.url AND i.status='used') AS used_items"
        " FROM feeds f ORDER BY LOWER(COALESCE(f.name, f.url))"
    ).fetchall()
    inventory = "".join(
        f'<div class="pod">{_cover(p["image_file"], p["name"] or p["url"])}'
        f'<span>{_e(p["name"] or p["url"])}</span>'
        + (f'<span class="badge">{p["used_items"]} featured</span>' if p["used_items"] else "")
        + "</div>"
        for p in pods
    )
    if editions:
        layout = f'<div class="editions">{"".join(cards)}</div>'
    else:
        layout = '<div class="empty">No editions yet. The first one appears after the next run.</div>'
    feed_url = f"{cfg.public_base_url}/feed.xml"
    stats = (f"{len(editions)} editions &middot; {total_stories} stories &middot; "
             f"following {len(pods)} podcasts")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_e(cfg.feed_title)}</title>"
        f'<meta name="description" content="{_e(description)}">'
        f'<meta property="og:title" content="{_e(cfg.feed_title)}">'
        f'<meta property="og:description" content="{_e(description)}">'
        + (f'<meta property="og:image" content="{_e(cover_url(cfg, absolute=True))}">'
           f'<link rel="icon" href="{_e(art)}"><link rel="apple-touch-icon" href="{_e(art)}">' if art else "")
        +
        f'<link rel="alternate" type="application/rss+xml" title="{_e(cfg.feed_title)}" href="feed.xml">'
        f"<style>{CSS}</style></head><body><div class=\"wrap\">"
        + (f'<header class="hero"><div class="logo"><img src="{_e(art)}" alt="{_e(cfg.feed_title)} cover"></div><div>'
           if art else '<header class="hero"><div class="logo" aria-hidden="true">Q</div><div>')
        +
        f"<h1>{_e(cfg.feed_title)}</h1>"
        f"<p>{_e(description)}</p>"
        '<div class="actions"><a class="btn primary" href="feed.xml">Subscribe via RSS</a>'
        f'<button class="btn copy" data-url="{_e(feed_url)}">Copy feed URL</button></div>'
        f'<div class="stats">{stats}</div></div></header>'
        f"<h2>Editions</h2>{layout}"
        f'<h2>Podcasts included ({len(pods)})</h2><div class="grid">{inventory}</div>'
        f"<footer>Updated {datetime.now(tz):%Y-%m-%d %H:%M} &middot; "
        "Keys: space play/pause, j/l &minus;/+15s, p/n previous/next story</footer>"
        f"</div><script>{JS}</script></body></html>"
    )


def write_index(conn: sqlite3.Connection, cfg: Config) -> str:
    """Write public/index.html and return its path."""
    cfg.public_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.public_dir / "index.html"
    path.write_text(render_index(conn, cfg), encoding="utf-8")
    return str(path)
