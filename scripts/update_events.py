#!/usr/bin/env python3
import json, re, sys
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources.json"
EVENTS = ROOT / "data" / "events.json"
STATUS = ROOT / "data" / "source_status.json"

MONTHS = {
    "gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,
    "luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12
}

# Espressioni ammesse: volutamente conservative.
GOOD = re.compile(
    r"open\s*day|giornat[ae]\s+di\s+orientamento|porte\s+aperte|lezion[ei]\s+aperte|student[ei]\s+per\s+un\s+giorno|visita\s+il\s+campus",
    re.I
)
BAD = re.compile(
    r"magistral|career\s*day|matricol|laureat|phd|dottorat|alumni|master\s+accademic|bienni?\s+specialistic",
    re.I
)
DATE_RE = re.compile(
    r"\b(?P<day>[0-3]?\d)\s+(?P<month>gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+(?P<year>20\d{2})\b",
    re.I
)

HEADERS = {
    "User-Agent":"Mozilla/5.0 (compatible; UniversitadriEvents/1.0; +https://github.com/fbegpt-dot/universitadri-events)"
}

def load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()

def block_text(node):
    return clean(node.get_text(" ", strip=True))

def extract_title(text):
    m = GOOD.search(text)
    if not m:
        return "Open Day / orientamento"
    start = max(0, m.start() - 55)
    end = min(len(text), m.end() + 85)
    title = clean(text[start:end]).strip(" -–—,:;")
    return title[:112].rstrip() + ("…" if len(title) > 112 else "")

def make_event(source, url, d, text):
    return {
        "institution": source["institution"],
        "title": extract_title(text),
        "date": d.isoformat(),
        "areas": source["areas"],
        "details": "Roma · verifica dettagli sulla fonte ufficiale",
        "url": url,
    }

def scrape_source(source):
    found = []
    statuses = []
    today = date.today()

    for url in source["urls"]:
        try:
            r = requests.get(url, timeout=25, headers=HEADERS)
            r.raise_for_status()
        except Exception as exc:
            print(f"WARN {source['institution']} {url}: {exc}", file=sys.stderr)
            statuses.append({"url": url, "status": "error", "message": str(exc)[:250]})
            continue

        statuses.append({"url": url, "status": "ok", "http_status": r.status_code})
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script","style","noscript","svg"]):
            tag.decompose()

        # Cerchiamo blocchi reali della pagina, non una singola stringa piatta.
        nodes = soup.find_all(["article","section","li","div","p","a"])
        for node in nodes:
            text = block_text(node)
            if len(text) < 12 or len(text) > 1200:
                continue
            if not GOOD.search(text) or BAD.search(text):
                continue

            for m in DATE_RE.finditer(text):
                try:
                    d = date(
                        int(m.group("year")),
                        MONTHS[m.group("month").lower()],
                        int(m.group("day"))
                    )
                except ValueError:
                    continue

                if d < today:
                    continue

                # La data deve stare vicina alla frase-evento nello stesso blocco.
                nearest = min(abs(m.start() - g.start()) for g in GOOD.finditer(text))
                if nearest > 170:
                    continue

                found.append(make_event(source, url, d, text))

    return found, statuses

def dedupe(events):
    # An institution/date/source combination represents one appointment.
    # Prefer a manually verified entry over a scraped description.
    chosen = {}
    for e in events:
        key = (e["institution"].casefold(), e["date"], e["url"].rstrip("/"))
        old = chosen.get(key)
        if old is None or (e.get("verified") is True and old.get("verified") is not True):
            chosen[key] = e
    return sorted(chosen.values(), key=lambda e: (e["date"], e["institution"]))


def main():
    sources = load_json(SOURCES, [])
    previous = load_json(EVENTS, {"events":[]})
    today = date.today()

    # Manteniamo solo gli eventi già verificati manualmente.
    kept = [
        e for e in previous.get("events", [])
        if e.get("date") and e["date"] >= today.isoformat() and e.get("verified") is True
    ]

    scraped = []
    checked = 0
    source_status = []
    for source in sources:
        checked += 1
        found, statuses = scrape_source(source)
        scraped.extend(found)
        source_status.append({"institution": source["institution"], "events_detected": len(found), "urls": statuses})

    merged = dedupe(kept + scraped)

    payload = {
        "last_updated": datetime.now().strftime("%d/%m/%Y"),
        "sources_checked": checked,
        "events": merged
    }

    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    EVENTS.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    STATUS.write_text(json.dumps({"last_updated": datetime.now().isoformat(timespec="seconds"), "institutions": source_status}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failures = sum(x["status"] == "error" for item in source_status for x in item["urls"])
    print(f"Saved {len(merged)} future events from {checked} institutions; {failures} source errors.")

if __name__ == "__main__":
    main()
