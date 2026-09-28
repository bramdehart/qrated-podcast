"""Static HTML homepage: channel header, edition list with player, and podcast inventory."""

from __future__ import annotations

import html
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Config
from .texts import mmss, spoken_date

CSS = """
:root{--bg:#fafaf7;--fg:#1c1c1e;--muted:#6b6b70;--card:#fff;--line:#e3e3dc;--accent:#5b4bdb}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececee;--muted:#9a9aa2;--card:#1e1e22;--line:#2e2e34;--accent:#9d8cff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:24px 16px 64px}
header h1{margin:0;font-size:2rem}header p{margin:.25rem 0 1rem;color:var(--muted)}
a{color:var(--accent)}.btn{display:inline-block;padding:.4rem .9rem;border:1px solid var(--accent);border-radius:999px;text-decoration:none}
h2{font-size:1.1rem;margin:2rem 0 .75rem}
.layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.4fr);gap:16px;align-items:start}
@media (max-width:720px){.layout{grid-template-columns:1fr}}
.list{display:flex;flex-direction:column;gap:8px}
.ep{display:block;width:100%;text-align:left;font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;cursor:pointer}
.ep[aria-current=true]{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.ep b{display:block}.ep small{color:var(--muted)}
.thumbs{display:flex;gap:4px;margin-top:6px;flex-wrap:wrap}
.thumbs img,.thumbs .ph{width:28px;height:28px;border-radius:6px;object-fit:cover;background:var(--line)}
.detail{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.detail h3{margin:0 0 .25rem}.detail audio{width:100%;margin:.75rem 0}
.item{display:flex;gap:12px;padding:10px 0;border-top:1px solid var(--line)}
.item img,.item .ph{width:56px;height:56px;border-radius:8px;object-fit:cover;flex:none;background:var(--line)}
.item p{margin:.2rem 0 0}.muted{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:14px}
.pod{text-align:center;font-size:.85rem}.pod img,.pod .ph{width:100%;aspect-ratio:1;border-radius:12px;object-fit:cover;background:var(--line);display:block}
.pod span{display:block;margin-top:4px;line-height:1.25}
.js .detail{display:none}.js .detail.on{display:block}
footer{margin-top:3rem;color:var(--muted);font-size:.85rem}
"""

JS = """
(function(){
  document.documentElement.classList.add('js');
  var eps=[].slice.call(document.querySelectorAll('.ep')),
      details=[].slice.call(document.querySelectorAll('.detail'));
  function show(id){
    details.forEach(function(d){var on=d.id==='ed-'+id;d.classList.toggle('on',on);
      if(!on){var a=d.querySelector('audio');if(a)a.pause();}});
    eps.forEach(function(e){e.setAttribute('aria-current',e.dataset.id===id?'true':'false');});
  }
  eps.forEach(function(e){e.addEventListener('click',function(){
    show(e.dataset.id);history.replaceState(null,'','#'+e.dataset.id);
    var d=document.getElementById('ed-'+e.dataset.id);
    if(window.innerWidth<=720&&d)d.scrollIntoView({behavior:'smooth'});});});
  var first=location.hash.slice(1);
  if(!eps.some(function(e){return e.dataset.id===first;}))first=eps.length?eps[0].dataset.id:'';
  if(first)show(first);
})();
"""


def _e(text) -> str:
    return html.escape(str(text if text is not None else ""))


def _cover(file: str | None, alt: str = "") -> str:
    if file:
        return f'<img src="covers/{_e(file)}" alt="{_e(alt)}" loading="lazy">'
    return '<div class="ph"></div>'


def render_index(conn: sqlite3.Connection, cfg: Config) -> str:
    tz = ZoneInfo(cfg.tz)
    editions = conn.execute("SELECT * FROM editions ORDER BY id DESC").fetchall()

    list_html, detail_html = [], []
    for ed in editions:
        items = conn.execute(
            "SELECT i.*, e.podcast, e.title AS episode_title, f.image_file FROM items i"
            " JOIN episodes e ON e.guid = i.episode_guid"
            " LEFT JOIN feeds f ON f.url = e.feed_url"
            " WHERE i.edition_id=? ORDER BY i.position",
            (ed["id"],),
        ).fetchall()
        created = datetime.fromisoformat(ed["created_at"]).astimezone(tz)
        when = f"{spoken_date(created)}, {created:%H:%M}"
        mins = max(1, round((ed["duration"] or 0) / 60))
        thumbs, seen = [], set()
        for it in items:
            if it["podcast"] not in seen:
                seen.add(it["podcast"])
                thumbs.append(_cover(it["image_file"], it["podcast"]))
        list_html.append(
            f'<button class="ep" data-id="{ed["id"]}" aria-current="false">'
            f'<b>{_e(when)}</b><small>{len(items)} stories from {len(seen)} shows &middot; {mins} min</small>'
            f'<span class="thumbs">{"".join(thumbs)}</span></button>'
        )
        rows = "".join(
            f'<div class="item">{_cover(it["image_file"], it["podcast"])}<div>'
            f'<b>{_e(it["title"])}</b><br><span class="muted">{_e(it["podcast"])} &mdash; '
            f'{_e(it["episode_title"])} ({mmss(it["start_sec"])}&ndash;{mmss(it["end_sec"])})</span>'
            f'<p>{_e(it["summary"])}</p></div></div>'
            for it in items
        )
        detail_html.append(
            f'<section class="detail" id="ed-{ed["id"]}"><h3>{_e(ed["title"])}</h3>'
            f'<span class="muted">{_e(when)} &middot; {mins} min</span>'
            f'<audio controls preload="none" src="editions/{_e(ed["file_name"])}"></audio>{rows}</section>'
        )

    pods = conn.execute(
        "SELECT f.name, f.url, f.image_file,"
        " (SELECT COUNT(*) FROM items i JOIN episodes e ON e.guid=i.episode_guid"
        "  WHERE e.feed_url=f.url AND i.status='used') AS used_items"
        " FROM feeds f ORDER BY LOWER(COALESCE(f.name, f.url))"
    ).fetchall()
    inventory = "".join(
        f'<div class="pod">{_cover(p["image_file"], p["name"] or "")}'
        f'<span>{_e(p["name"] or p["url"])}'
        + (f'<br><small class="muted">{p["used_items"]} featured</small>' if p["used_items"] else "")
        + "</span></div>"
        for p in pods
    )
    if editions:
        layout = (
            f'<div class="layout"><div class="list">{"".join(list_html)}</div>'
            f'<div>{"".join(detail_html)}</div></div>'
        )
    else:
        layout = '<p class="muted">No editions yet. The first one appears after the next run.</p>'
    feed_url = f"{cfg.public_base_url}/feed.xml"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_e(cfg.feed_title)}</title>"
        f'<link rel="alternate" type="application/rss+xml" title="{_e(cfg.feed_title)}" href="feed.xml">'
        f"<style>{CSS}</style>"
        "<noscript><style>.detail{display:block!important;margin-bottom:12px}</style></noscript>"
        '</head><body><div class="wrap">'
        f"<header><h1>{_e(cfg.feed_title)}</h1>"
        "<p>A daily selection of the best fragments from the podcasts I follow.</p>"
        '<a class="btn" href="feed.xml">Subscribe via RSS</a> '
        f'<span class="muted">{_e(feed_url)}</span></header>'
        f"<h2>Episodes</h2>{layout}"
        f'<h2>Podcasts included ({len(pods)})</h2><div class="grid">{inventory}</div>'
        f"<footer>Generated {datetime.now(tz):%Y-%m-%d %H:%M}</footer>"
        f"</div><script>{JS}</script></body></html>"
    )


def write_index(conn: sqlite3.Connection, cfg: Config) -> str:
    """Write public/index.html and return its path."""
    cfg.public_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.public_dir / "index.html"
    path.write_text(render_index(conn, cfg), encoding="utf-8")
    return str(path)
