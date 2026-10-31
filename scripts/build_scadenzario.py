#!/usr/bin/env python3
import json, re
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "data" / "events.json"
MANUAL = ROOT / "data" / "manual_deadlines.json"
OUT = ROOT / "data" / "scadenzario.json"

EXCLUDE = re.compile(r"global governance|magistral|career|master|post.?laurea", re.I)

def load(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def key(item):
    return (
        item.get("institution","").strip().lower(),
        item.get("kind",""),
        item.get("date",""),
        re.sub(r"\W+","",item.get("title","").lower())[:70]
    )

def main():
    today = date.today().isoformat()
    events = load(EVENTS, {"events":[]})
    manual = load(MANUAL, {"items":[],"waiting":[]})

    items = []

    # Open Day/orientamento già raccolti dal monitor: solo area Economia.
    for e in events.get("events", []):
        if "Economia" not in e.get("areas", []):
            continue
        if not e.get("date") or e["date"] < today:
            continue
        if EXCLUDE.search(e.get("title","")):
            continue
        items.append({
            "institution": e.get("institution",""),
            "kind": "open_day",
            "date": e["date"],
            "title": e.get("title","Open Day / orientamento"),
            "details": e.get("details","Roma"),
            "url": e.get("url",""),
            "verified": bool(e.get("verified", False)),
            "source": "monitor"
        })

    # Date verificate manualmente: ammissioni, test e appuntamenti ufficiali
    # che il crawler Open Day non intercetta in modo affidabile.
    for item in manual.get("items", []):
        if item.get("date") and item["date"] >= today:
            x = dict(item)
            x["source"] = "verified"
            items.append(x)

    # Deduplica senza cancellare eventi diversi nello stesso giorno.
    seen, merged = set(), []
    for item in sorted(items, key=lambda x:(x.get("date",""), x.get("institution",""), x.get("kind",""))):
        k = key(item)
        if k in seen:
            continue
        seen.add(k)
        merged.append(item)

    payload = {
        "last_updated": datetime.now().strftime("%d/%m/%Y"),
        "scope": "Economia e Management — Roma",
        "items": merged,
        "waiting": manual.get("waiting", [])
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scadenzario: {len(merged)} appuntamenti futuri.")

if __name__ == "__main__":
    main()
