from pathlib import Path

p = Path("CHANGELOG.md")
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
# Drop the shorter duplicate FHIR line (the fuller entry above it survives).
dup = "- FHIR clinical resources (`fhir_clinical.py`): Patient/Condition/Medication/Encounter/Device parsing, bundle\u2192EHR bridge, paginated authenticated extraction with retry/backoff + manifests.\n"
assert sum(1 for l in lines if l == dup) == 1, "duplicate line not found exactly once"
lines.remove(dup)
p.write_text("".join(lines), encoding="utf-8")
print("duplicate FHIR entry removed")
