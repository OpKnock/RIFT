# Public dataset examples

`public_example.csv` is a **synthetic format example**, not real patient data.
`public_real_bidsleep.csv` is a **tiny real-data example** scraped from the
public BIDSleep PhysioNet dataset (3 nights, median HR only) to prove the
`PublicDatasetSource` → `DigitalTwin` path works on independently published
open data. Other fields are blank — the twin handles missingness via
baseline imputation and input-quality flags, as tested.
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
