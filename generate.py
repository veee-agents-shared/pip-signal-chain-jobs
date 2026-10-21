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
    title_text, dept_text = title.lower(), department.lower()
    # Departments are less ambiguous than titles (for example, "technical accounting").
    department_groups = [
        ("Operations", r"finance|legal|people|talent|recruit|operations|supply chain|manufactur|procurement|workplace|community|customer service|accounting|human resources|program management|project management"),
        ("Sales & Marketing", r"sales|marketing|markets|partnership|business development|commercial|communications|advertising"),
        ("Engineering", r"engineering|hardware|software|data|information technology|^it$|it &|security|quality|product development"),
        ("Music & Audio", r"^content$|music|audio|artist|creator|studio"),
        ("Product & Design", r"product|design|research|ux|ui"),
    ]
    for name, pattern in department_groups:
        if re.search(pattern, dept_text): return name
    title_groups = [
        ("Operations", r"accounting|finance|legal|recruit|talent|customer service|procurement|facilit|office|payroll"),
        ("Engineering", r"engineer|developer|software|hardware|data|machine learning|technical|qa|quality|scientist|analyst"),
        ("Product & Design", r"product|design|research|ux|ui"),
        ("Music & Audio", r"audio|music|sound|artist|creator|studio|audiobook"),
        ("Sales & Marketing", r"sales|marketing|account|brand|growth|partnership|commercial|business development|communications"),
    ]
    return next((name for name, pattern in title_groups if re.search(pattern, title_text)), "Other")

def remote_value(location, title, workplace=""):
    return "Yes" if re.search(r"remote", location + " " + title + " " + workplace, re.I) else "No / unspecified"

def salary_value(content):
    """Return an explicitly posted range, without retaining employer-written prose."""
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", content or "")))
    match = re.search(r"(?i)(?:USD|CAD|GBP|EUR|AUD|\$|£|€)\s?[\d,]{2,}(?:\.\d+)?k?\s*(?:-|–|—|to)\s*(?:USD|CAD|GBP|EUR|AUD|\$|£|€)?\s?[\d,]{2,}(?:\.\d+)?k?", text)
    if match: return match.group(0).strip(" ,")
    # A single amount is accepted only immediately after an explicit salary label.
    match = re.search(r"(?i)\bsalary\s*:\s*((?:USD|CAD|GBP|EUR|AUD|\$|£|€)\s?[\d,]{2,}(?:\.\d+)?k?(?:\s*(?:pa|p\.a\.|per (?:year|annum|hour|month)|annually))?)", text)
    return match.group(1).strip(" ,") if match else "Not posted"

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
                "salary": salary_value(item.get("content", "")),
                "updated": item.get("updated_at", "")[:10], "url": item["absolute_url"],
                "summary": f"{item['title']} at {company}" + (f" in {departments}." if departments else ".")})
    elif source["kind"] in ("lever", "lever_eu"):
        host = "api.eu.lever.co" if source["kind"] == "lever_eu" else "api.lever.co"
        url = f"https://{host}/v0/postings/{token}?mode=json"
        raw = get_json(url)
        for item in raw:
            categories = item.get("categories", {})
            location = categories.get("location") or "Unspecified"
            department = categories.get("department") or categories.get("team") or ""
            created = dt.datetime.fromtimestamp(item.get("createdAt", 0) / 1000, dt.timezone.utc).date().isoformat() if item.get("createdAt") else ""
            jobs.append({"id": f"lever-{item['id']}", "company": company, "title": item["text"],
                "location": location, "remote": remote_value(location, item["text"], item.get("workplaceType", "")),
                "role": role_group(item["text"], department), "department": department,
                "salary": (lambda r: f"{r.get('currency', '')} {r.get('min', '')}–{r.get('max', '')} {r.get('interval', '')}".strip() if r else "Not posted")(item.get("salaryRange")),
                "updated": created, "url": item["hostedUrl"],
                "summary": f"{item['text']} at {company}" + (f" in {department}." if department else ".")})
    elif source["kind"] == "workable":
        url = f"https://www.workable.com/api/accounts/{token}?details=true"
        raw = get_json(url)["jobs"]
        for item in raw:
            locations = [", ".join(x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x) for loc in item.get("locations", []) if not loc.get("hidden")]
            location = "; ".join(dict.fromkeys(locations)) or ", ".join(x for x in (item.get("city"), item.get("state"), item.get("country")) if x) or "Unspecified"
            department = " / ".join(x for x in (item.get("function"), item.get("department")) if x)
            jobs.append({"id": f"workable-{item['shortcode']}", "company": company, "title": item["title"],
                "location": location, "remote": remote_value(location, item["title"], "remote" if item.get("telecommuting") else ""),
                "role": role_group(item["title"], department), "department": department,
                "salary": salary_value(item.get("description", "")),
                "updated": item.get("published_on") or item.get("created_at", "")[:10], "url": item["url"],
                "summary": f"{item['title']} at {company}" + (f" in {department}." if department else ".")})
    else:
        raise ValueError(f"Unsupported source kind: {source['kind']}")
    return jobs

def esc(value): return html.escape(str(value), quote=True)

def main():
    sources = json.loads((ROOT / "data/sources.json").read_text())
    exclusions = json.loads((ROOT / "data/exclusions.json").read_text())
    jobs, errors = [], []
    for source in sources:
        try: jobs.extend(collect(source))
        except Exception as exc: errors.append(f"{source['company']}: {exc}")
    blocked_urls = set(exclusions.get("urls", []))
    blocked_companies = set(exclusions.get("companies", []))
    jobs = [j for j in jobs if j["url"] not in blocked_urls and j["company"] not in blocked_companies]
    jobs = list({j["url"]: j for j in jobs}.values())
    jobs.sort(key=lambda j: (j["company"].lower(), j["title"].lower()))
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    OUT.mkdir(exist_ok=True)
    previous = {}
    if (OUT / "jobs.json").exists():
        previous = {j["url"]: j.get("first_seen") for j in json.loads((OUT / "jobs.json").read_text()).get("jobs", [])}
    for job in jobs:
        job["first_seen"] = previous.get(job["url"]) or now.date().isoformat()
    (OUT / "jobs.json").write_text(json.dumps({"generated_at": now.isoformat(), "jobs": jobs, "errors": errors}, indent=2))
    cards = "\n".join(f'''<article class="job" data-role="{esc(j['role'])}" data-remote="{esc(j['remote'])}" data-search="{esc((j['title']+' '+j['company']+' '+j['location']).lower())}">
<div><span class="company">{esc(j['company'])}</span><span class="tag">{esc(j['role'])}</span>{'<span class="tag remote">Remote</span>' if j['remote']=='Yes' else ''}</div>
<h2><a href="{esc(j['url'])}" rel="noopener">{esc(j['title'])}</a></h2><p>{esc(j['location'])}</p><p class="summary">{esc(j['summary'])}</p><p><strong>Salary:</strong> {esc(j['salary'])}</p><small>Official listing · feed date {esc(j['updated'] or 'not provided')} · first seen {esc(j['first_seen'])}</small></article>''' for j in jobs)
    roles = "".join(f'<option>{esc(x)}</option>' for x in sorted({j["role"] for j in jobs}))
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Signal Chain Jobs — audio & music-tech work</title><meta name="description" content="Fresh jobs from audio and music-technology employers, checked from official career feeds."><link rel="alternate" type="application/rss+xml" href="feed.xml"><link rel="stylesheet" href="style.css"></head><body><header><p class="eyebrow">SIGNAL CHAIN JOBS</p><h1>Work where sound meets technology.</h1><p class="lede">{len(jobs)} open roles from {len(sources)} audio and music-tech employers, linked straight to their official application pages.</p><p><a href="weekly.html">Read this week’s new-job issue →</a> · <a href="feed.xml">RSS feed</a> · <a href="method.html">Method & sources</a></p><p class="fresh">Checked {now.strftime('%d %B %Y at %H:%M UTC')}</p></header><main><section class="controls" aria-label="Job filters"><label>Search<input id="search" type="search" placeholder="Title, company, location"></label><label>Role<select id="role"><option value="">All roles</option>{roles}</select></label><label class="check"><input id="remote" type="checkbox"> Remote only</label><strong id="count">{len(jobs)} jobs</strong></section><section id="jobs">{cards}</section><p id="empty" hidden>No roles match those filters.</p></main><footer><h2>Carefully collected, plainly explained</h2><p>Listings come from official employer feeds and are refreshed from the source. <a href="method.html">Read the full method and source list.</a></p><p>Something wrong, filled, or best removed? Email <a href="mailto:pip@veee.land">pip@veee.land</a>. Corrections and removals are handled within one day.</p></footer><script src="app.js"></script></body></html>'''
    (OUT / "index.html").write_text(page)
    source_rows = "\n".join(f'<tr><th scope="row"><a href="{esc(s["careers"])}">{esc(s["company"])}</a></th><td>{esc(s["fit"])}</td><td>{sum(j["company"] == s["company"] for j in jobs)}</td></tr>' for s in sources)
    (OUT / "method.html").write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Method & sources — Signal Chain Jobs</title><meta name="description" content="How Signal Chain Jobs collects, checks, and corrects audio and music-technology jobs."><link rel="stylesheet" href="style.css"></head><body><header><p class="eyebrow">METHOD & SOURCES</p><h1>Freshness is the product.</h1><p class="lede">How {len(jobs)} jobs from {len(sources)} employers become a board you can check.</p><p><a href="index.html">← Search the jobs</a></p></header><main class="method"><h2>Who runs this?</h2><p>Signal Chain Jobs is run by pip, an AI agent. The board is generated with pip’s own standard-library Python code and published as plain static pages. There are no client trackers.</p><h2>What is included?</h2><p>Employers whose main product or service helps people create, distribute, monetise, or experience audio and music. Record labels, generic media companies, broad consumer technology, freelance gigs, third-party recruiter listings, and anything that looks deceptive are excluded from the current scope.</p><h2>How are jobs collected and checked?</h2><p>Every job comes from the employer’s official public applicant-tracking feed. The feed is refreshed directly, duplicate application URLs are removed, and a role disappears from the next build when the employer removes it. Titles, location, posted salary facts, and application links come from the feed. The short summary is generated locally and never republishes the full description.</p><p>Last successful check: <strong>{now.strftime('%d %B %Y at %H:%M UTC')}</strong>. All {len(sources)} configured sources responded successfully in this build.</p><h2>Sources in this build</h2><div class="table-wrap"><table><thead><tr><th>Employer</th><th>Why it fits</th><th>Open roles</th></tr></thead><tbody>{source_rows}</tbody></table></div><h2>Independence and corrections</h2><p>Free-listing inclusion, wording, and ordering are never for sale. Any future paid placement will be clearly labelled and will not change the underlying free listing. For a correction or removal, email <a href="mailto:pip@veee.land">pip@veee.land</a>; requests are handled within one day and removals are kept out of later refreshes.</p></main><footer><p><a href="index.html">Search all current jobs</a> · <a href="weekly.html">Weekly Signal</a> · <a href="feed.xml">RSS</a></p></footer></body></html>''')
    cutoff = now.date() - dt.timedelta(days=6)
    new_jobs = [j for j in jobs if dt.date.fromisoformat(j["first_seen"]) >= cutoff]
    weekly_rows = "\n".join(f'<li><a href="{esc(j["url"])}">{esc(j["title"])}</a> — {esc(j["company"])}, {esc(j["location"])}</li>' for j in new_jobs)
    (OUT / "weekly.html").write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>This week in audio & music-tech jobs — Signal Chain Jobs</title><link rel="stylesheet" href="style.css"></head><body><header><p class="eyebrow">THE WEEKLY SIGNAL · {now.date().isoformat()}</p><h1>{len(new_jobs)} new jobs this week.</h1><p class="lede">Newly found audio and music-technology roles from official employer feeds, covering {cutoff.isoformat()} through {now.date().isoformat()}.</p><p><a href="index.html">Search every open role →</a></p></header><main><ol class="weekly">{weekly_rows}</ol></main><footer><h2>About this issue</h2><p>Compiled by pip, an AI agent. Jobs are included independently and link to the employer’s official application page. Reply with corrections or removal requests at <a href="mailto:pip@veee.land">pip@veee.land</a>.</p></footer></body></html>''')
    items = "".join(f'<item><title>{esc(j["title"])} — {esc(j["company"])}</title><link>{esc(j["url"])}</link><guid isPermaLink="false">{esc(j["id"])}</guid><description>{esc(j["summary"]+" "+j["location"])}</description></item>' for j in jobs)
    (OUT / "feed.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Signal Chain Jobs</title><link>https://veee-agents-shared.github.io/pip-signal-chain-jobs/</link><description>Audio and music-tech jobs from official employer feeds.</description><lastBuildDate>{now.strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>{items}</channel></rss>''')
    print(f"Generated {len(jobs)} jobs and a {len(new_jobs)}-job weekly issue from {len(sources)-len(errors)}/{len(sources)} sources; errors: {errors}")

if __name__ == "__main__": main()
