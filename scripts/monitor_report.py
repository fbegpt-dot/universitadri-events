#!/usr/bin/env python3
"""Produce a durable, machine-readable report for the weekly monitor."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORT = DATA / "monitor_report.json"

def read(name, fallback):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback

def identity(item):
    return "|".join(str(item.get(k, "")).strip().casefold() for k in ("institution", "kind", "date", "title", "url"))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scrape", default="unknown")
    parser.add_argument("--build", default="unknown")
    parser.add_argument("--commit", default="unknown")
    parser.add_argument("--deploy", default="unknown")
    parser.add_argument("--run-url", default="")
    args = parser.parse_args()

    previous = read("monitor_report.json", {})
    schedule = read("scadenzario.json", {})
    source = read("source_status.json", {})
    items = schedule.get("items", [])
    today = datetime.now(timezone.utc).date().isoformat()
    future = [i for i in items if i.get("date", "") >= today]
    old = set(previous.get("event_keys", []))
    keys = [identity(i) for i in future]
    new = [dict(i) for i in future if identity(i) not in old] if previous.get("event_keys") is not None else []
    errors = [{"institution": s.get("institution"), "url": u.get("url"), "message": u.get("message", "")}
              for s in source.get("institutions", []) for u in s.get("urls", []) if u.get("status") != "ok"]
    steps = {"scrape": args.scrape, "build": args.build, "data_commit": args.commit, "pages_deploy": args.deploy}
    success = all(v == "success" for v in steps.values())
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_url": args.run_url,
        "status": "success" if success else "failed",
        "steps": steps,
        "source_checked_at": source.get("last_updated"),
        "published_data_updated_at": schedule.get("last_updated"),
        "future_events_count": len(future),
        "new_events_count": len(new),
        "new_events": new,
        "comparison_available": previous.get("event_keys") is not None,
        "source_errors_count": len(errors),
        "source_errors": errors,
        "event_keys": keys,
        "note": "pages_deploy=success confirms GitHub Pages deployment step, not an independent HTTP check of the public URL."
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Monitor: {report['status']}; {len(future)} future; {len(new)} new; {len(errors)} source errors.")

if __name__ == "__main__":
    main()
