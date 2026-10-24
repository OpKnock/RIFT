"""Regression guards for the hosted RIFT simulation demo UI."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "stitch-ui"


def test_render_ui_uses_the_configured_render_api_not_a_visitor_localhost():
    source = (UI / "rift-live.js").read_text(encoding="utf-8")
    assert 'return "https://rift-s2fw.onrender.com";' in source
    assert 'hostname === "rift-ui.onrender.com"' in source


def test_run_history_is_not_deleted_on_every_page_load():
    source = (UI / "rift-live.js").read_text(encoding="utf-8")
    assert 'localStorage.removeItem("rift_simulation_run_history_v1")' not in source


def test_schema_loading_has_a_timeout_and_visible_fallback_state():
    source = (UI / "simulation.html").read_text(encoding="utf-8")
    assert "function fetchWithTimeout(" in source
    assert "Promise.race([" in source
    assert "Fallback bounds ready; checking engine..." in source
    assert "Timed out. Using fallback bounds." in source
    assert "API unavailable. Using fallback bounds." in source
    assert "initializeSimulationConsole()" in source


def test_fresh_run_clears_old_results_and_reports_a_completion_timestamp():
    source = (UI / "simulation.html").read_text(encoding="utf-8")
    assert 'id="run-status"' in source
    assert "function clearDisplayedResults()" in source
    assert "Fresh API response received at" in source
    assert "No new results are available" in source

def test_absent_clear_history_button_cannot_abort_simulation_initialization():
    source = (UI / "simulation.html").read_text(encoding="utf-8")
    assert "const clearHistoryButton = document.getElementById('btn-clear-history');" in source
    assert "if (clearHistoryButton) {" in source
    assert "initializeSimulationConsole()" in source
