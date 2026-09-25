# Archived debug/exploration tooling

One-off PhysioNet probing scripts (`check_*.py`, `fetch_resources.py`) and
early scraper prototypes (`quick_scrape_*.py`) from the real-data ingestion
work. Kept for audit history; NOT part of the build, tests, or CI.

Canonical commands live in `src/rift/health/*_scrape.py`:

- `python -m rift.health.bidsleep_scrape`
- `python -m rift.health.wearable_exam_stress_scrape`
- `python -m rift.health.sepsis_challenge_scrape`
- `python -m rift.health.physionet_cardiac_scrape`
