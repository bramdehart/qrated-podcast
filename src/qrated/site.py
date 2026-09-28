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
:root{--bg:#fff;--fg:#1d1d1f;--muted:#6e6e73;--line:rgba(0,0,0,.1);--fill:#f5f5f7;--fill-2:#e8e8ed;
--accent:#8a2ecb;--accent-soft:rgba(138,46,203,.1);--on-accent:#fff;--art-line:rgba(0,0,0,.08);
--tip-bg:rgba(29,29,31,.94);--tip-fg:#fff;--shadow:0 4px 14px rgba(0,0,0,.08),0 1px 3px rgba(0,0,0,.06);
--font:-apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",system-ui,sans-serif;
--font-display:-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#1c1c1e;--fg:#f5f5f7;--muted:#98989d;--line:rgba(255,255,255,.12);
--fill:#2c2c2e;--fill-2:#3a3a3c;--accent:#c77dff;--accent-soft:rgba(199,125,255,.14);--on-accent:#1c1c1e;
--art-line:rgba(255,255,255,.1);--tip-bg:rgba(58,58,60,.96);--shadow:0 4px 14px rgba(0,0,0,.4)}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 var(--font);-webkit-font-smoothing:antialiased}
.wrap{max-width:980px;margin:0 auto;padding:40px 20px 80px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}button{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.hero{display:grid;grid-template-columns:260px minmax(0,1fr);gap:36px;align-items:end;padding-bottom:32px;border-bottom:1px solid var(--line)}
@media (max-width:700px){.hero{grid-template-columns:1fr;gap:20px}.hero .logo{width:200px;height:200px}}
.logo{width:260px;height:260px;border-radius:12px;overflow:hidden;box-shadow:var(--shadow);display:grid;place-items:center;
color:#fff;font:700 96px/1 var(--font-display);background:linear-gradient(135deg,#8a2ecb,#e0477a);border:1px solid var(--art-line)}
.logo img{width:100%;height:100%;object-fit:cover;display:block}
.kicker{font-size:.72rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.hero h1{margin:.15rem 0 .1rem;font:700 2.3rem/1.1 var(--font-display);letter-spacing:-.025em}
.author{font-size:1.05rem;color:var(--accent);font-weight:500}
.hero p{margin:.8rem 0 1.1rem;color:var(--muted);max-width:60ch}
.actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.btn{display:inline-flex;align-items:center;gap:7px;height:36px;padding:0 16px;border-radius:999px;border:0;
background:var(--fill);color:var(--fg);cursor:pointer;font-size:.9rem;font-weight:600;text-decoration:none!important}
.btn:hover{background:var(--fill-2)}
.btn svg{width:17px;height:17px;fill:currentColor;flex:none}
.btn i{display:grid}.btn .ok,.btn.done .cp{display:none}.btn.done .ok{display:block}
.btn.primary{background:var(--accent);color:var(--on-accent)}.btn.primary:hover{filter:brightness(1.08)}
.stats{margin-top:1rem}
h2{font:700 1.4rem/1.2 var(--font-display);letter-spacing:-.015em;margin:2.4rem 0 .4rem}
h2 small{font:500 .95rem var(--font);color:var(--muted);letter-spacing:0;margin-left:6px}
.editions{border-bottom:1px solid var(--line)}
.edition{border-top:1px solid var(--line)}
.edition>summary{list-style:none;display:flex;gap:16px;align-items:flex-start;padding:18px 4px;cursor:pointer}
.edition>summary::-webkit-details-marker{display:none}
.edition>summary:focus-visible{outline-offset:-2px;border-radius:8px}
.ep-main{flex:1;min-width:0}
.ep-title{display:block;font-size:1.1rem;font-weight:600;letter-spacing:-.01em;margin:.1rem 0 .2rem}
.edition>summary:hover .ep-title{color:var(--accent)}
.ep-desc{margin:0;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.ep-foot{display:flex;align-items:center;gap:14px;margin-top:12px;flex-wrap:wrap}
.row-play{display:inline-flex;align-items:center;gap:6px;height:30px;padding:0 12px 0 9px;border-radius:999px;border:0;cursor:pointer;
background:var(--accent-soft);color:var(--accent);font-size:.82rem;font-weight:600;font-variant-numeric:tabular-nums}
.row-play:hover{background:var(--accent);color:var(--on-accent)}
.row-play i{display:grid}.row-play svg{width:16px;height:16px;fill:currentColor}
.stack{display:flex;padding-left:6px}
.stack img,.stack .ph{width:28px;height:28px;border-radius:6px;object-fit:cover;margin-left:-6px;border:2px solid var(--bg);font-size:.75rem}
.chev{flex:none;width:28px;height:28px;margin-top:22px;border-radius:50%;display:grid;place-items:center;color:var(--muted);transition:transform .2s}
.chev svg{width:22px;height:22px;fill:currentColor}.edition[open] .chev{transform:rotate(180deg)}
.edition-body{padding:0 0 22px}
.ph{background:var(--fill-2);display:grid;place-items:center;color:var(--muted);font-weight:700}
.ph.q{background:linear-gradient(135deg,#8a2ecb,#e0477a);color:#fff}
.muted{color:var(--muted)}
.fallback-audio{width:100%;margin:4px 0 8px}
.player{display:none;position:sticky;top:8px;z-index:2;background:var(--fill);border-radius:14px;padding:14px 16px 10px}
.now{display:flex;gap:12px;align-items:center;min-height:56px}
.now .art{width:56px;height:56px;border-radius:8px;object-fit:cover;flex:none;border:1px solid var(--art-line)}
.now>div{min-width:0}
.now small{display:block;color:var(--accent);font-weight:600;font-size:.7rem;text-transform:uppercase;letter-spacing:.06em}
.now b{display:block;font-weight:600;line-height:1.25;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.now span{display:block;color:var(--muted);font-size:.85rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.timeline{position:relative;margin:30px 0 4px;height:22px;cursor:pointer;touch-action:none;outline:none}
.marks{position:absolute;left:0;right:0;top:-26px;height:22px}
.marks img,.marks .ph{position:absolute;width:22px;height:22px;border-radius:5px;object-fit:cover;transform:translateX(-2px);
border:1.5px solid var(--fill);font-size:9px;cursor:pointer;transition:transform .12s}
.marks img:hover,.marks .ph:hover,.marks .on{transform:translateX(-2px) scale(1.4);z-index:1;box-shadow:var(--shadow)}
.bar{position:absolute;left:0;right:0;top:8px;height:6px;border-radius:99px;background:var(--fill-2);overflow:hidden}
.seg{position:absolute;top:0;bottom:0;border-left:2px solid var(--fill);transition:background .15s}
.seg.k-item:nth-child(odd){background:color-mix(in srgb,var(--accent) 30%,var(--fill-2))}
.seg.k-item:nth-child(even){background:color-mix(in srgb,var(--accent) 18%,var(--fill-2))}
.seg.hot{background:color-mix(in srgb,var(--accent) 55%,var(--fill-2))!important}
.fill{position:absolute;left:0;top:0;bottom:0;background:var(--accent);width:0}
.head{position:absolute;top:4px;z-index:1;width:14px;height:14px;border-radius:50%;background:#fff;left:0;
transform:translateX(-7px) scale(.75);box-shadow:0 1px 4px rgba(0,0,0,.35);transition:transform .12s}
.timeline:hover .head,.timeline:focus-visible .head{transform:translateX(-7px) scale(1)}
.ghost{position:absolute;top:4px;bottom:4px;width:2px;border-radius:1px;background:var(--fg);opacity:0;pointer-events:none}
.tip{position:absolute;bottom:36px;left:0;width:260px;display:flex;gap:10px;padding:10px;border-radius:12px;background:var(--tip-bg);
color:var(--tip-fg);box-shadow:var(--shadow);-webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px);opacity:0;pointer-events:none;
transform:translateY(4px);transition:opacity .12s,transform .12s;z-index:3}
.tip.on{opacity:1;transform:none}.timeline.hovering .ghost{opacity:.3}
.tip img,.tip .ph{width:50px;height:50px;border-radius:7px;object-fit:cover;flex:none}
.tip>div{min-width:0}
.tip b{display:block;font-size:.86rem;font-weight:600;line-height:1.25;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tip span{display:block;font-size:.76rem;opacity:.7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tip small{font-size:.72rem;opacity:.55;font-variant-numeric:tabular-nums}
.controls{display:flex;align-items:center;gap:4px}
.ctl{width:34px;height:34px;border-radius:50%;border:0;background:transparent;cursor:pointer;display:grid;place-items:center;color:var(--fg)}
.ctl:hover{background:var(--fill-2)}.ctl svg{width:20px;height:20px;fill:currentColor}
.ctl.play{width:42px;height:42px;background:var(--fg);color:var(--bg)}.ctl.play:hover{background:var(--fg);opacity:.85}
.ctl.play svg{width:22px;height:22px}
.time{font-variant-numeric:tabular-nums;color:var(--muted);font-size:.8rem;margin-left:8px}
.dl{color:var(--muted)}.dl:hover{color:var(--fg)}
.speed{margin-left:auto;border:0;background:var(--fill-2);border-radius:99px;height:26px;padding:0 10px;cursor:pointer;
font-size:.75rem;font-weight:600;font-variant-numeric:tabular-nums}
.stories{list-style:none;margin:10px 0 0;padding:0}
.item{display:flex;gap:14px;padding:12px 8px;border-radius:10px;align-items:flex-start}
.item+.item{box-shadow:0 -1px 0 var(--line)}
.item.has-t{cursor:pointer}.item.has-t:hover{background:var(--fill)}
.item.playing{background:var(--accent-soft);box-shadow:none}.item.playing+.item{box-shadow:none}
.item.playing b{color:var(--accent)}
.item .art{width:52px;height:52px;border-radius:8px;object-fit:cover;flex:none;border:1px solid var(--art-line)}
.item>div{min-width:0}.item b{font-weight:600}
.item .meta{color:var(--muted);font-size:.82rem;margin-top:1px}.item p{margin:.3rem 0 0;font-size:.9rem;color:var(--muted)}
.item .at{font-variant-numeric:tabular-nums;font-size:.8rem;color:var(--muted);margin-left:auto;padding-left:8px;flex:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:22px 18px;margin-top:14px}
.pod{font-size:.85rem;min-width:0}
.pod .art{width:100%;aspect-ratio:1;border-radius:10px;object-fit:cover;display:block;border:1px solid var(--art-line);font-size:1.8rem}
.pod span{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-top:7px;line-height:1.3}
.pod small{display:block;color:var(--muted);font-size:.78rem;margin-top:1px}
.pod .ph.art{display:grid}
@media (max-width:520px){.grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:16px 12px}.pod{font-size:.78rem}}
.empty{padding:28px;text-align:center;border-radius:14px;background:var(--fill);color:var(--muted);margin-top:14px}
footer{margin-top:3.5rem;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:.78rem}
.row-reels{display:inline-flex;align-items:center;gap:6px;height:30px;padding:0 12px 0 9px;border-radius:999px;border:0;
cursor:pointer;background:var(--fill);color:var(--fg);font-size:.82rem;font-weight:600}
.row-reels:hover{background:var(--fill-2)}.row-reels i{display:grid}.row-reels svg{width:16px;height:16px;fill:currentColor}
.reels-open,.reels-open body{overflow:hidden}
.reels{position:fixed;inset:0;z-index:50;background:#000;color:#fff}
.reels[hidden]{display:none}
.reels-frame{position:relative;max-width:480px;height:100vh;height:100dvh;margin:0 auto;overflow:hidden}
.reels-scroll{height:100%;overflow-y:scroll;scroll-snap-type:y mandatory;overscroll-behavior:contain;scrollbar-width:none}
.reels-scroll::-webkit-scrollbar{display:none}
.reel{position:relative;height:100%;scroll-snap-align:start;scroll-snap-stop:always;overflow:hidden;cursor:pointer;
display:flex;flex-direction:column;padding:72px 22px 28px}
.reel-bg{position:absolute;inset:-60px;background:#2c2c2e center/cover;filter:blur(40px) saturate(1.3);transform:scale(1.15)}
.reel-shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.35) 0%,rgba(0,0,0,.15) 35%,rgba(0,0,0,.8) 100%)}
.reel-center{position:relative;flex:1;display:grid;place-items:center;min-height:0}
.reel-art{width:min(68vw,290px);max-height:100%;aspect-ratio:1;border-radius:16px;object-fit:cover;
box-shadow:0 20px 50px rgba(0,0,0,.5);background:linear-gradient(135deg,#8a2ecb,#e0477a);font-size:5rem;color:#fff}
.reel-art.ph{display:grid;place-items:center;font-weight:700}
.reel.on .reel-art{animation:reel-in .45s ease-out}
@keyframes reel-in{from{transform:scale(.94);opacity:.6}to{transform:none;opacity:1}}
.reel-info{position:relative;padding-right:56px}
.reel-show{display:flex;align-items:center;gap:8px;font-weight:600;font-size:.9rem}
.reel-show img{width:26px;height:26px;border-radius:6px;object-fit:cover;border:1px solid rgba(255,255,255,.3)}
.reel h3{margin:.55rem 0 .35rem;font:700 1.45rem/1.2 var(--font-display);letter-spacing:-.015em}
.reel p{margin:0;font-size:.95rem;line-height:1.4;color:rgba(255,255,255,.85);display:-webkit-box;-webkit-line-clamp:3;
-webkit-box-orient:vertical;overflow:hidden}
.reel small{display:block;margin-top:.45rem;color:rgba(255,255,255,.6);font-size:.8rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.reel-progress{display:flex;align-items:center;gap:10px;margin-top:16px}
.reel-bar{flex:1;height:3px;border-radius:2px;background:rgba(255,255,255,.28);overflow:hidden}
.reel-bar i{display:block;height:100%;width:0;background:#fff}
.reel-time{font-size:.75rem;font-variant-numeric:tabular-nums;color:rgba(255,255,255,.75);min-width:42px;text-align:right}
.reel-paused{position:absolute;left:50%;top:45%;width:84px;height:84px;margin:-42px 0 0 -42px;border-radius:50%;
background:rgba(0,0,0,.45);display:grid;place-items:center;opacity:0;transition:opacity .15s;pointer-events:none}
.reel-paused svg{width:44px;height:44px;fill:#fff}
.reels.paused .reel.on .reel-paused{opacity:1}
.reels-top{position:absolute;top:0;left:0;right:0;z-index:2;display:flex;align-items:center;gap:10px;padding:14px 14px 0}
.reels-meta{display:flex;flex-direction:column;line-height:1.2;text-shadow:0 1px 3px rgba(0,0,0,.5)}
.reels-meta b{font-size:.95rem}.reels-meta span{font-size:.78rem;opacity:.75}
.reels-btn{width:42px;height:42px;border-radius:50%;border:0;display:grid;place-items:center;cursor:pointer;
background:rgba(255,255,255,.16);color:#fff;-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px)}
.reels-btn:hover{background:rgba(255,255,255,.28)}.reels-btn svg{width:22px;height:22px;fill:currentColor}
.reels-btn:focus-visible{outline:2px solid #fff;outline-offset:2px}
.reels-rail{position:absolute;right:14px;bottom:96px;z-index:2;display:flex;flex-direction:column;gap:12px}
.reels .i-play,.reels.paused .i-pause{display:none}.reels.paused .i-play{display:grid}.reels .i-pause{display:grid}
.reels-nav{display:none}
@media (min-width:700px){.reels-frame{overflow:visible}.reels-nav{position:absolute;left:calc(100% + 20px);top:50%;
transform:translateY(-50%);display:flex;flex-direction:column;gap:12px}.reels-prev svg{transform:none}
.reels-next svg{transform:rotate(180deg)}}
@media (min-width:700px){.reels-scroll{border-radius:0}}
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
      rows=[].slice.call(sec.querySelectorAll('.stories .item')),rowBtn=sec.querySelector('.row-play'),
      rowIcon=rowBtn&&rowBtn.querySelector('i'),rowLabel=rowBtn&&rowBtn.querySelector('span'),chapters=data.chapters,dur=data.duration||0,cur=-2,dragging=false,pending=null;
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
      if(rowLabel&&t>0)rowLabel.textContent=Math.max(1,Math.ceil((T-t)/60))+' min left';
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
    audio.addEventListener('play',function(){playBtn.innerHTML=ICON.pause;playBtn.setAttribute('aria-label','Pause');
      if(rowIcon){rowIcon.innerHTML=ICON.pause;rowBtn.setAttribute('aria-label','Pause episode');}});
    audio.addEventListener('pause',function(){playBtn.innerHTML=ICON.play;playBtn.setAttribute('aria-label','Play');
      if(rowIcon){rowIcon.innerHTML=ICON.play;rowBtn.setAttribute('aria-label','Play episode');}});
    if(rowBtn)rowBtn.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();
      if(!sec.open)sec.open=true;toggle();});
    audio.addEventListener('ended',function(){audio.pause();});
    render();if(cur===-2)setNow(-1);
    var api={audio:audio,data:data,play:play,toggle:toggle,jump:jump,seek:seek,
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

  var latest=document.querySelector('.play-latest');
  if(latest&&editions.length){var ld=editions[0],lp=players[ld.dataset.id],li=latest.querySelector('i'),ll=latest.querySelector('span');
    latest.addEventListener('click',function(){if(!ld.open)ld.open=true;lp.toggle();});
    lp.audio.addEventListener('play',function(){li.innerHTML=ICON.pause;ll.textContent='Pause';});
    lp.audio.addEventListener('pause',function(){li.innerHTML=ICON.play;ll.textContent='Resume';});}

  document.addEventListener('keydown',function(e){if(e.metaKey||e.ctrlKey||e.altKey)return;
    if(reel){var k=e.key;
      if(k==='ArrowDown'||k==='j'||k==='PageDown'){e.preventDefault();goTo(reel.cur+1);}
      else if(k==='ArrowUp'||k==='k'||k==='PageUp'){e.preventDefault();goTo(reel.cur-1);}
      else if(k===' '){e.preventDefault();reel.p.toggle();}
      else if(k==='Escape'){e.preventDefault();closeReels();}
      return;}
    if(!active)return;
    var t=e.target.tagName;if(t==='INPUT'||t==='TEXTAREA'||t==='BUTTON'||t==='A'||t==='SUMMARY'||e.target.getAttribute('role')==='slider')return;
    if(e.key===' '||e.key==='k'){e.preventDefault();active.toggle();}
    else if(e.key==='j')active.seek(active.audio.currentTime-15);else if(e.key==='l')active.seek(active.audio.currentTime+15);
    else if(e.key==='n')active.jump(1);else if(e.key==='p')active.jump(-1);});

  // Reels: full-screen vertical feed, one story per slide, autoplay from the story's announcement.
  var R=document.querySelector('.reels'),RS=R&&R.querySelector('.reels-scroll'),reel=null;
  function slideHtml(c,n,total){
    var art=c.art?'<img class="reel-art" src="'+c.art+'" alt="">':
      '<div class="reel-art ph">'+esc((c.podcast||'?').charAt(0))+'</div>';
    var avatar=c.art?'<img src="'+c.art+'" alt="">':'';
    return '<section class="reel" data-n="'+n+'" aria-label="Story '+(n+1)+' of '+total+'">'+
      (c.art?'<div class="reel-bg" style="background-image:url(\''+c.art+'\')"></div>':'<div class="reel-bg"></div>')+
      '<div class="reel-shade"></div><div class="reel-center">'+art+'</div>'+
      '<div class="reel-info"><div class="reel-show">'+avatar+'<span>'+esc(c.podcast)+'</span></div>'+
      '<h3>'+esc(c.title)+'</h3><p>'+esc(c.summary||'')+'</p><small>'+esc(c.episode||'')+'</small>'+
      '<div class="reel-progress"><div class="reel-bar"><i></i></div><span class="reel-time"></span></div></div>'+
      '<div class="reel-paused" aria-hidden="true">'+ICON.play+'</div></section>';}
  function storyAt(t){if(!reel)return 0;for(var i=reel.stories.length-1;i>=0;i--)if(t>=reel.stories[i].start)return i;return 0;}
  function goTo(n){if(!reel||n<0||n>=reel.stories.length||reel.advancing===n)return;reel.advancing=n;
    reel.slides[n].scrollIntoView({behavior:'smooth',block:'start'});}
  function activate(n){if(!reel||reel.cur===n)return;reel.cur=n;reel.advancing=null;var c=reel.stories[n];
    reel.slides.forEach(function(s,j){s.classList.toggle('on',j===n);});
    R.querySelector('.reels-count').textContent=(n+1)+' / '+reel.stories.length;
    reel.p.seek(c.start);reel.p.play();}
  function tick(){if(!reel||reel.cur<0)return;var a=reel.p.audio,t=a.currentTime,c=reel.stories[reel.cur],
      len=Math.max(1,c.end-c.start),f=Math.max(0,Math.min(1,(t-c.start)/len)),s=reel.slides[reel.cur];
    s.querySelector('.reel-bar i').style.width=(f*100)+'%';
    s.querySelector('.reel-time').textContent='-'+fmt(Math.max(0,c.end-t));
    if(!a.paused&&t>=c.end-0.3&&reel.cur<reel.stories.length-1)goTo(reel.cur+1);}
  function syncPaused(){if(reel)R.classList.toggle('paused',reel.p.audio.paused);}
  function openReels(id){var p=players[id];if(!R||!p)return;
    var stories=p.data.chapters.filter(function(c){return c.kind==='item';});if(!stories.length)return;
    if(reel)closeReels(true);
    RS.innerHTML=stories.map(function(c,n){return slideHtml(c,n,stories.length);}).join('');
    var slides=[].slice.call(RS.querySelectorAll('.reel'));
    reel={p:p,id:id,stories:stories,slides:slides,cur:-1,advancing:null};
    R.querySelector('.reels-date').textContent=p.data.date||'';
    R.hidden=false;root.classList.add('reels-open');
    history.pushState({reels:true},'');
    var start=p.audio.currentTime>0?storyAt(p.audio.currentTime):0;
    RS.scrollTop=slides[start].offsetTop;
    reel.obs=new IntersectionObserver(function(es){es.forEach(function(e){
      if(e.isIntersecting&&e.intersectionRatio>=0.6)activate(+e.target.dataset.n);});},{root:RS,threshold:[0.6]});
    slides.forEach(function(s){reel.obs.observe(s);
      s.addEventListener('click',function(){reel.p.toggle();});});
    p.audio.addEventListener('timeupdate',tick);p.audio.addEventListener('play',syncPaused);p.audio.addEventListener('pause',syncPaused);
    activate(start);syncPaused();R.querySelector('.reels-close').focus();}
  function closeReels(fromHistory){if(!reel)return;var p=reel.p,id=reel.id;
    reel.obs.disconnect();p.audio.removeEventListener('timeupdate',tick);
    p.audio.removeEventListener('play',syncPaused);p.audio.removeEventListener('pause',syncPaused);
    reel=null;R.hidden=true;root.classList.remove('reels-open');RS.innerHTML='';
    if(!fromHistory&&history.state&&history.state.reels)history.back();
    return id;}
  if(R){
    [].slice.call(document.querySelectorAll('[data-reels]')).forEach(function(b){b.addEventListener('click',function(e){
      e.preventDefault();e.stopPropagation();openReels(b.dataset.reels);});});
    R.querySelector('.reels-close').addEventListener('click',function(){closeReels();});
    R.querySelector('.reels-toggle').addEventListener('click',function(){if(reel)reel.p.toggle();});
    R.querySelector('.reels-prev').addEventListener('click',function(){if(reel)goTo(reel.cur-1);});
    R.querySelector('.reels-next').addEventListener('click',function(){if(reel)goTo(reel.cur+1);});
    R.querySelector('.reels-episode').addEventListener('click',function(){var id=closeReels();
      var d=document.getElementById('ed-'+id);if(d){d.open=true;d.scrollIntoView({block:'start'});}});
    window.addEventListener('popstate',function(){if(reel)closeReels(true);});}

  var copy=document.querySelector('.copy');
  if(copy&&navigator.clipboard)copy.addEventListener('click',function(){navigator.clipboard.writeText(copy.dataset.url).then(function(){
    var label=copy.querySelector('span'),t=label.textContent;copy.classList.add('done');label.textContent='Copied';
    setTimeout(function(){copy.classList.remove('done');label.textContent=t;},1500);});});
  else if(copy)copy.hidden=true;
})();
"""

ICON_PLAY = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>'
ICON_PREV = '<svg viewBox="0 0 24 24"><path d="M6 6h2v12H6zm3.5 6 8.5 6V6z"/></svg>'
ICON_DOWNLOAD = '<svg viewBox="0 0 24 24"><path d="M11 4h2v9l3.5-3.5 1.4 1.4L12 16.8 6.1 10.9l1.4-1.4L11 13zM5 18h14v2H5z"/></svg>'
ICON_REELS = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 2h10a3 3 0 0 1 3 3v14a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V5'
              'a3 3 0 0 1 3-3zm0 2a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1zm3 4.5 5 3.5-5 3.5z"/></svg>')
ICON_CLOSE = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 6.4 17.6 5 12 10.6 6.4 5 5 6.4 10.6 12 5 17.6 '
              '6.4 19 12 13.4 17.6 19 19 17.6 13.4 12z"/></svg>')
ICON_LIST = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5h2v2H3zm4 0h14v2H7zm-4 6h2v2H3zm4 0h14v2H7zm-4 6h2v2H3zm4 0h14v2H7z"/></svg>'
ICON_UP = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7.4 15.4 12 10.8l4.6 4.6L18 14l-6-6-6 6z"/></svg>'
ICON_PAUSE = '<svg viewBox="0 0 24 24"><path d="M6 5h4v14H6zm8 0h4v14h-4z"/></svg>'
ICON_CHEVRON = '<svg viewBox="0 0 24 24"><path d="M7.4 8.6 12 13.2l4.6-4.6L18 10l-6 6-6-6z"/></svg>'
ICON_RSS = ('<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="18" r="2.2"/>'
            '<path d="M4 10.5v2.7a6.8 6.8 0 0 1 6.8 6.8h2.7A9.5 9.5 0 0 0 4 10.5zm0-5.3v2.7A12.1 12.1 0 0 1 16.1 20h2.7'
            'A14.8 14.8 0 0 0 4 5.2z"/></svg>')
ICON_COPY = ('<svg class="cp" viewBox="0 0 24 24" aria-hidden="true"><path d="M16 1H4a2 2 0 0 0-2 2v14h2V3h12zm3 4H8'
             'a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H8V7h11z"/></svg>'
             '<svg class="ok" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/></svg>')
ICON_NEXT = '<svg viewBox="0 0 24 24"><path d="M6 18l8.5-6L6 6zm10-12h2v12h-2z"/></svg>'


REELS_MARKUP = (
    '<div class="reels" role="dialog" aria-modal="true" aria-label="Story reels" hidden><div class="reels-frame">'
    '<div class="reels-top"><button class="reels-btn reels-close" type="button" aria-label="Close reels">'
    + ICON_CLOSE + '</button><div class="reels-meta"><b class="reels-count"></b><span class="reels-date"></span></div></div>'
    '<div class="reels-scroll"></div>'
    '<div class="reels-rail"><button class="reels-btn reels-toggle" type="button" aria-label="Play or pause">'
    '<span class="i-pause">' + ICON_PAUSE + '</span><span class="i-play">' + ICON_PLAY + '</span></button>'
    '<button class="reels-btn reels-episode" type="button" aria-label="Show episode">' + ICON_LIST + '</button></div>'
    '<div class="reels-nav"><button class="reels-btn reels-prev" type="button" aria-label="Previous story">' + ICON_UP
    + '</button><button class="reels-btn reels-next" type="button" aria-label="Next story">' + ICON_UP + '</button></div>'
    "</div></div>"
)


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
            "podcast": it["podcast"], "summary": it["summary"], "episode": it["episode_title"],
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
        eyebrow = f"{created:%b} {created.day}, {created:%Y}" + (" &middot; Latest" if idx == 0 else "")
        titles = " &middot; ".join(_e(it["title"]) for it in items)
        summary = (
            f'<summary><div class="ep-main"><div class="kicker">{eyebrow}</div>'
            f'<span class="ep-title">{_e(spoken_date(created))}</span>'
            f'<p class="ep-desc">{len(items)} stories from {len(seen)} shows: {titles}</p>'
            f'<div class="ep-foot"><button class="row-play" type="button" aria-label="Play episode">'
            f'<i>{ICON_PLAY}</i><span>{mins} min</span></button>'
            + (f'<button class="row-reels" type="button" data-reels="{ed["id"]}" aria-label="Watch as reels">'
               f'<i>{ICON_REELS}</i><span>Reels</span></button>' if chapters else "")
            + f'<span class="stack">{"".join(stack)}</span></div></div>'
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
        data = {"title": ed["title"], "date": spoken_date(created), "duration": duration, "chapters": chapters}
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
        + (f'<small>{p["used_items"]} {"story" if p["used_items"] == 1 else "stories"} featured</small>'
           if p["used_items"] else "")
        + "</div>"
        for p in pods
    )
    if editions:
        layout = f'<div class="editions">{"".join(cards)}</div>'
    else:
        layout = '<div class="empty">No editions yet. The first one appears after the next run.</div>'
    feed_url = f"{cfg.public_base_url}/feed.xml"
    updated = datetime.fromisoformat(editions[0]["created_at"]).astimezone(tz) if editions else None
    stats = " &middot; ".join(
        ["Daily", f'{len(editions)} episode{"" if len(editions) == 1 else "s"}', f"{total_stories} stories",
         f"{len(pods)} shows"] + ([f"Updated {updated:%b} {updated.day}"] if updated else [])
    )
    latest_has_chapters = bool(editions) and conn.execute(
        "SELECT COUNT(*) FROM items WHERE edition_id=? AND chapter_start IS NULL", (editions[0]["id"],)
    ).fetchone()[0] == 0 and conn.execute(
        "SELECT COUNT(*) FROM items WHERE edition_id=?", (editions[0]["id"],)).fetchone()[0] > 0
    reels_btn = (f'<button class="btn open-reels" type="button" data-reels="{editions[0]["id"]}">'
                 f'<i>{ICON_REELS}</i><span>Reels</span></button>' if latest_has_chapters else "")
    latest_btn = (f'<button class="btn primary play-latest" type="button"><i>{ICON_PLAY}</i>'
                  "<span>Latest Episode</span></button>" if editions else "")
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
        '<div class="kicker">Podcast</div>'
        f"<h1>{_e(cfg.feed_title)}</h1>"
        f'<div class="author">Curated for {_e(cfg.listener_name)}</div>'
        f"<p>{_e(description)}</p>"
        f'<div class="actions">{latest_btn}{reels_btn}'
        f'<a class="btn" href="feed.xml">{ICON_RSS}<span>Subscribe</span></a>'
        f'<button class="btn copy" type="button" data-url="{_e(feed_url)}">{ICON_COPY}<span>Copy feed URL</span></button></div>'
        f'<div class="kicker stats">{stats}</div></div></header>'
        f"<h2>Episodes</h2>{layout}"
        f'<h2>Shows in the mix <small>{len(pods)}</small></h2><div class="grid">{inventory}</div>'
        f"<footer>Updated {datetime.now(tz):%Y-%m-%d %H:%M} &middot; "
        "Keys: space play/pause, j/l &minus;/+15s, p/n previous/next story</footer>"
        f"</div>{REELS_MARKUP}<script>{JS}</script></body></html>"
    )


def write_index(conn: sqlite3.Connection, cfg: Config) -> str:
    """Write public/index.html and return its path."""
    cfg.public_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.public_dir / "index.html"
    path.write_text(render_index(conn, cfg), encoding="utf-8")
    return str(path)
