import sqlite3
import unittest
from collect import DirectoryParser, key_for, upsert


class CollectorTests(unittest.TestCase):
    def test_parse_and_upsert(self):
        p = DirectoryParser()
        p.feed('<article class="record"><span class="name">Alex Lee</span><span class="email">A@EXAMPLE.ORG</span></article>')
        self.assertEqual(p.records[0]["name"], "Alex Lee")
        with sqlite3.connect(":memory:") as db:
            upsert(db, p.records, "https://example.org", "2026-10-22")
            upsert(db, [{"name":"Alex Lee","email":"a@example.org"}], "https://example.org", "2026-10-23")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)

    def test_normalized_key(self):
        self.assertEqual(key_for({"name":" Alex  Lee ","organisation":"City"}), "alex lee|city")

