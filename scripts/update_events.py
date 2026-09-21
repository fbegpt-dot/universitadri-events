#!/usr/bin/env python3
import json, re, html, sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources.json"
EVENTS = ROOT / "data" / "events.json"

MONTHS = {
    "gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,
    "luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12
}
GOOD = re.compile(r"open\s*day|orientament|porte\s+aperte|lezion[ei]\s+apert|student[ei]\s+per\s+un\s+giorno|visita\s+il\s+campus|workshop", re.I)
BAD = re.compile(r"magistral|career\s*day|matricol|laureat|phd|dottorat|alumni", re.I)
DATE_RE = re.compile(
    r"\b(?P<day>[0-3]?\d)\s+(?P<month>gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(?P<year>20\d{2})\b",
    re.I
)

HEADERS = {"User-Agent":"Mozilla/5.0 (compatible; UniversitadriEvents/1.0; +https://github.com/fbegpt-dot/universitadri-events)"}

def load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()

def make_event(source, url, d, context):
    context = clean(context)
    title = "Open Day / orientamento"
    m = re.search(r"([^.!?]{0,90}(?:open\s*day|orientament\w*|porte\s+aperte|lezion[ei]\s+apert\w*|workshop)[^.!?]{0,90})", context, re.I)
    if m:
        title = clean(m.group(1)).strip(" -–—,:;")
        if len(title) > 115:
            title = title[:112].rstrip() + "…"
    return {
        "institution": source["institution"],
        "title": title,
        "date": d.isoformat(),
        "areas": source["areas"],
        "details": "Roma · verifica dettagli sulla fonte ufficiale",
        "url": url,
    }

def scrape_source(source):
    found = []
    today = date.today()
    for url in source["urls"]:
        try:
            r = requests.get(url, timeout=25, headers=HEADERS)
            r.raise_for_status()
        except Exception as exc:
            print(f"WARN {source['institution']} {url}: {exc}", file=sys.stderr)
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script","style","noscript","svg"]):
            tag.decompose()
        text = clean(soup.get_text(" ", strip=True))

        for m in DATE_RE.finditer(text):
            try:
                d = date(int(m.group("year")), MONTHS[m.group("month").lower()], int(m.group("day")))
            except ValueError:
                continue
            if d < today:
                continue

            start, end = max(0, m.start()-220), min(len(text), m.end()+220)
            context = text[start:end]
            if not GOOD.search(context) or BAD.search(context):
                continue
            found.append(make_event(source, url, d, context))
    return found

def dedupe(events):
    seen, out = set(), []
    for e in sorted(events, key=lambda x:(x["date"], x["institution"], x["title"])):
        key = (e["institution"].lower(), e["date"], re.sub(r"\W+","",e["title"].lower())[:60])
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out

def main():
    sources = load_json(SOURCES, [])
    previous = load_json(EVENTS, {"events":[]})
    today = date.today()

    # Manteniamo gli eventi futuri già verificati, poi aggiungiamo ciò che il crawler trova.
    kept = [e for e in previous.get("events", []) if e.get("date") and e["date"] >= today.isoformat()]
    scraped = []
    checked = 0
    for source in sources:
        checked += 1
        scraped.extend(scrape_source(source))

    merged = dedupe(kept + scraped)
    payload = {
        "last_updated": datetime.now().strftime("%d/%m/%Y"),
        "sources_checked": checked,
        "events": merged
    }
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    EVENTS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(merged)} future events from {checked} institutions.")

if __name__ == "__main__":
    main()
