# Public Records Collection Pipeline

Collect records from public directory pages with `robots.txt` checks, a descriptive user agent, one-request-per-second pacing, retry backoff, and source attribution. The parser expects `.record` elements with `.name`, `.title`, `.organisation`, and `.email` fields. SQLite upserts normalized records and tracks fetch time.

```sh
python collect.py https://example.org/directory --db records.db
python collect.py --fixture examples/directory.html --source https://example.org/directory --db records.db
python -m unittest discover -s tests -v
```

The fixture mode allows inspection without contacting a website. The default crawler processes one page at a time; it does not include a distributed task broker. Similarity-based merging is limited to records sharing a normalized email or matching name and organisation above the configured cutoff.

