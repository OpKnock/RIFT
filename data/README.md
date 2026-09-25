# Public dataset examples

`public_example.csv` is a **synthetic format example**, not real patient data.
`public_real_bidsleep.LEGACY.csv` is a **retired artifact**: it mislabels
BIDSleep instantaneous HR as `resting_hr` and raw acceleration as
`activity_load`. It is kept for audit history only — do NOT use it for
validation. Regenerate with `python -m rift.health.bidsleep_scrape`,
which emits the canonical schema (`heart_rate` + experimental
`accel_magnitude_mean`, provenance-only, never `activity_load`) with
subject identity and provenance.
It re-uses the synthetic 60-day external series (seed 123) written as the
strict CSV schema `PublicDatasetSource` expects:

```
day_index,resting_hr,hrv_rmssd,sleep_hours,activity_load
```

Use it to test the public-data pathway without a real dataset:

```python
from rift.health.sources import PublicDatasetSource
from rift.health.ehr import demo_ehr, normalize_ehr
from rift.health.twin import DigitalTwin

source = PublicDatasetSource("data/public_example.csv")
ehr, _ = normalize_ehr(demo_ehr())
twin = DigitalTwin(ehr, source)
print(twin.update(30))
```

Replace this file with a governed public dataset that follows the same
header — the twin, Guardian, and evaluation layers work unchanged.
Never claim this file is clinical evidence: `docs/evidence-sheet.md`
and `/api/twin/evidence` label it `synthetic-external-v1`.
