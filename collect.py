"""Respectful public directory collector with provenance and deduplication."""
import argparse
import difflib
import html.parser
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path


USER_AGENT = "PortfolioRecordsCollector/1.0 (public directory research)"
SCHEMA = """CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY,name TEXT,title TEXT,organisation TEXT,email TEXT,source_url TEXT,fetched_at TEXT,record_key TEXT UNIQUE);"""


class DirectoryParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.records = []
        self.record = None
        self.field = None

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "").split()
        if "record" in classes:
            self.record = {}
        if self.record is not None:
            self.field = next((key for key in ("name", "title", "organisation", "email") if key in classes), self.field)

    def handle_endtag(self, tag):
        if tag == "article" and self.record is not None:
            if self.record.get("name"):
                self.records.append(self.record)
            self.record = None
        self.field = None

    def handle_data(self, data):
        if self.record is not None and self.field:
            self.record[self.field] = (self.record.get(self.field, "") + data).strip()


def normalize(text):
    return re.sub(r"\s+", " ", text.casefold().strip())


def key_for(record):
    email = normalize(record.get("email", ""))
    return email or normalize(record["name"]) + "|" + normalize(record.get("organisation", ""))


def upsert(db, records, source, fetched_at=None, cutoff=0.92):
    fetched_at = fetched_at or datetime.now(timezone.utc).isoformat()
    db.executescript(SCHEMA)
    count = 0
    with db:
        for record in records:
            key = key_for(record)
            if not key:
                continue
            existing = db.execute("SELECT record_key FROM records WHERE record_key=?", (key,)).fetchone()
            if not existing and not record.get("email"):
                existing = next((row for row in db.execute("SELECT record_key FROM records WHERE email='' OR email IS NULL")
                                 if difflib.SequenceMatcher(None, row[0], key).ratio() >= cutoff), None)
            if existing:
                key = existing[0]
            db.execute("""INSERT INTO records(name,title,organisation,email,source_url,fetched_at,record_key)
               VALUES(?,?,?,?,?,?,?) ON CONFLICT(record_key) DO UPDATE SET title=excluded.title,source_url=excluded.source_url,fetched_at=excluded.fetched_at""",
               (record["name"], record.get("title", ""), record.get("organisation", ""), record.get("email", ""), source, fetched_at, key))
            count += 1
    return count


def fetch(url, opener=urllib.request.urlopen, sleep=time.sleep):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("HTTP(S) URL required")
    robots = urllib.robotparser.RobotFileParser()
    robots.set_url(urllib.parse.urljoin(url, "/robots.txt"))
    robots.read()
    if not robots.can_fetch(USER_AGENT, url):
        raise PermissionError("robots.txt disallows this page")
    for attempt in range(3):
        sleep(1 if attempt == 0 else 2 ** attempt)
        try:
            with opener(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=15) as response:
                return response.read(2_000_000).decode("utf-8", errors="replace")
        except Exception:
            if attempt == 2:
                raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("url", nargs="?")
    p.add_argument("--fixture")
    p.add_argument("--source")
    p.add_argument("--db", default="records.db")
    a = p.parse_args()
    if not a.url and not a.fixture:
        p.error("provide URL or --fixture")
    source = a.source or a.url
    if not source:
        p.error("--fixture also needs --source")
    page = Path(a.fixture).read_text(encoding="utf-8") if a.fixture else fetch(a.url)
    parser = DirectoryParser()
    parser.feed(page)
    with sqlite3.connect(a.db) as db:
        upsert(db, parser.records, source)
    print(json.dumps({"parsed": len(parser.records), "source": source}))


if __name__ == "__main__":
    main()

