"""Evidence bundle tests: manifest integrity, signing discipline, rendering."""
from rift.health import evidence as EV


def _bundle():
    return EV.build_bundle(
        model={"model_id": "cardiac-strain-v1", "weights_digest": "x"},
        dataset={"source_id": "synthetic-external-v1", "days_evaluated": 59, "events": 5},
        metrics={"event_agreement": 0.9},
        calibration={"method": "platt", "fit_window": "days 30-44"},
        gate={"clinical_use": "closed"},
        notes="unit-test bundle",
    )


def test_bundle_manifest_and_determinism():
    first, second = _bundle(), _bundle()
    assert first["manifest"]["bundle_version"] == "evidence-bundle-v1"
    assert first["manifest"]["signed"] is False
    assert first["manifest"]["signature"] is None
    assert first == second  # deterministic: same inputs, same bundle
    assert len(first["manifest"]["content_hash"]) == 64


def test_unsigned_stays_unsigned_and_tamper_detected():
    bundle = _bundle()
    assert EV.verify_bundle(bundle)["valid"] is True
    assert EV.verify_bundle(bundle)["signed"] is False
    tampered = {"manifest": dict(bundle["manifest"]), "body": dict(bundle["body"])}
    tampered["body"] = dict(tampered["body"], metrics={"event_agreement": 1.0})
    assert EV.verify_bundle(tampered)["valid"] is False


def test_sign_verify_roundtrip_and_wrong_key(monkeypatch):
    monkeypatch.setenv("RIFT_EVIDENCE_SIGNING_KEY", "test-key")
    signed = EV.sign_bundle(_bundle())
    assert signed["manifest"]["signed"] is True
    assert EV.verify_bundle(signed)["valid"] is True
    assert EV.verify_bundle(signed, key="wrong-key")["valid"] is False


def test_no_key_means_explicitly_unsigned(monkeypatch):
    monkeypatch.delenv("RIFT_EVIDENCE_SIGNING_KEY", raising=False)
    bundle = EV.sign_bundle(_bundle())
    assert bundle["manifest"]["signed"] is False
    assert EV.verify_bundle(bundle)["reason"].startswith("unsigned bundle")


def test_markdown_rendering_names_model_and_gate():
    text = EV.render_markdown(_bundle())
    assert "cardiac-strain-v1" in text
    assert "closed" in text
    assert "UNSIGNED" in text
