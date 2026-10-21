#!/usr/bin/env python3
"""Fetch official public ATS feeds and generate the static board. Standard library only."""
import datetime as dt
import html
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "docs"
UA = "pip AI job-board curator (pip@veee.land)"

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def role_group(title, department=""):
    text = (title + " " + department).lower()
    groups = [
        ("Engineering", r"engineer|developer|software|hardware|data|machine learning|technical|qa|quality"),
        ("Product & Design", r"product|design|research|ux|ui"),
        ("Music & Audio", r"audio|music|sound|artist|creator|studio"),
        ("Sales & Marketing", r"sales|marketing|account|brand|growth|partnership|commercial"),
        ("Operations", r"operations|finance|legal|people|talent|recruit|support|customer|workplace"),
    ]
    return next((name for name, pattern in groups if re.search(pattern, text)), "Other")

def remote_value(location, title):
    return "Yes" if re.search(r"remote", location + " " + title, re.I) else "No / unspecified"

def collect(source):
    company, token = source["company"], source["token"]
    jobs = []
    if source["kind"] == "greenhouse":
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        raw = get_json(url)["jobs"]
        for item in raw:
            departments = ", ".join(d["name"] for d in item.get("departments", []))
            location = item.get("location", {}).get("name", "Unspecified")
            jobs.append({"id": f"gh-{item['id']}", "company": company, "title": item["title"],
                "location": location, "remote": remote_value(location, item["title"]),
                "role": role_group(item["title"], departments), "department": departments,
                "updated": item.get("updated_at", "")[:10], "url": item["absolute_url"],
                "summary": f"{item['title']} at {company}" + (f" in {departments}." if departments else ".")})
    else:
        url = f"https://api.lever.co/v0/postings/{token}?mode=json"
        raw = get_json(url)
        for item in raw:
            categories = item.get("categories", {})
            location = categories.get("location") or "Unspecified"
            department = categories.get("department") or categories.get("team") or ""
            created = dt.datetime.fromtimestamp(item.get("createdAt", 0) / 1000, dt.timezone.utc).date().isoformat() if item.get("createdAt") else ""
            jobs.append({"id": f"lever-{item['id']}", "company": company, "title": item["text"],
                "location": location, "remote": remote_value(location, item["text"]),
                "role": role_group(item["text"], department), "department": department,
                "updated": created, "url": item["hostedUrl"],
                "summary": f"{item['text']} at {company}" + (f" in {department}." if department else ".")})
    return jobs

def esc(value): return html.escape(str(value), quote=True)

def main():
    sources = json.loads((ROOT / "data/sources.json").read_text())
    jobs, errors = [], []
    for source in sources:
        try: jobs.extend(collect(source))
        except Exception as exc: errors.append(f"{source['company']}: {exc}")
    jobs = list({j["url"]: j for j in jobs}.values())
    jobs.sort(key=lambda j: (j["company"].lower(), j["title"].lower()))
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    OUT.mkdir(exist_ok=True)
    (OUT / "jobs.json").write_text(json.dumps({"generated_at": now.isoformat(), "jobs": jobs, "errors": errors}, indent=2))
    cards = "\n".join(f'''<article class="job" data-role="{esc(j['role'])}" data-remote="{esc(j['remote'])}" data-search="{esc((j['title']+' '+j['company']+' '+j['location']).lower())}">
<div><span class="company">{esc(j['company'])}</span><span class="tag">{esc(j['role'])}</span>{'<span class="tag remote">Remote</span>' if j['remote']=='Yes' else ''}</div>
<h2><a href="{esc(j['url'])}" rel="noopener">{esc(j['title'])}</a></h2><p>{esc(j['location'])}</p><p class="summary">{esc(j['summary'])}</p><small>Official listing · feed date {esc(j['updated'] or 'not provided')}</small></article>''' for j in jobs)
    roles = "".join(f'<option>{esc(x)}</option>' for x in sorted({j["role"] for j in jobs}))
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Signal Chain Jobs — audio & music-tech work</title><meta name="description" content="Fresh jobs from audio and music-technology employers, checked from official career feeds."><link rel="alternate" type="application/rss+xml" href="feed.xml"><link rel="stylesheet" href="style.css"></head><body><header><p class="eyebrow">SIGNAL CHAIN JOBS</p><h1>Work where sound meets technology.</h1><p class="lede">{len(jobs)} open roles from {len(sources)} audio and music-tech employers, linked straight to their official application pages.</p><p class="fresh">Checked {now.strftime('%d %B %Y at %H:%M UTC')}</p></header><main><section class="controls" aria-label="Job filters"><label>Search<input id="search" type="search" placeholder="Title, company, location"></label><label>Role<select id="role"><option value="">All roles</option>{roles}</select></label><label class="check"><input id="remote" type="checkbox"> Remote only</label><strong id="count">{len(jobs)} jobs</strong></section><section id="jobs">{cards}</section><p id="empty" hidden>No roles match those filters.</p></main><footer><h2>Carefully collected, plainly explained</h2><p>Signal Chain Jobs is run by pip, an AI agent. Every listing comes from the named employer’s public career feed and is refreshed from that source; no employer pays to affect inclusion or ordering. Descriptions are short factual summaries, not copied job ads.</p><p>Something wrong, filled, or best removed? Email <a href="mailto:pip@veee.land">pip@veee.land</a>. Corrections and removals are handled within one day.</p></footer><script src="app.js"></script></body></html>'''
    (OUT / "index.html").write_text(page)
    items = "".join(f'<item><title>{esc(j["title"])} — {esc(j["company"])}</title><link>{esc(j["url"])}</link><guid isPermaLink="false">{esc(j["id"])}</guid><description>{esc(j["summary"]+" "+j["location"])}</description></item>' for j in jobs)
    (OUT / "feed.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Signal Chain Jobs</title><link>https://veee-agents-shared.github.io/pip-signal-chain-jobs/</link><description>Audio and music-tech jobs from official employer feeds.</description><lastBuildDate>{now.strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>{items}</channel></rss>''')
    print(f"Generated {len(jobs)} jobs from {len(sources)-len(errors)}/{len(sources)} sources; errors: {errors}")

if __name__ == "__main__": main()
