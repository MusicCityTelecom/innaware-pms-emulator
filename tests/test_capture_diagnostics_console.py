from innaware_pms_emulator.capture_diagnostics_console import html
from innaware_pms_emulator.main import app, index


def test_capture_analysis_console_is_read_only_and_uses_bounded_report_api():
    page = html()

    assert "Analyze Capture" in page
    assert "Read-only analysis." in page
    assert "/api/v1/interfaces" in page
    assert (
        "/api/v1/interfaces/${encodeURIComponent(name)}/capture-diagnostics"
        "?limit=${encodeURIComponent(limit)}"
    ) in page
    assert "suggested_actions" in page
    assert "confidence" in page
    assert "observations" in page

    # This view is intentionally GET-only. It must not grow interface-control,
    # traffic-generation, profile-switching, or configuration-write behavior.
    assert "method:'POST'" not in page
    assert 'method:"POST"' not in page
    assert "method:'PUT'" not in page
    assert 'method:"PUT"' not in page
    assert "method:'DELETE'" not in page
    assert 'method:"DELETE"' not in page
    assert "/start" not in page
    assert "/stop" not in page
    assert "/send/" not in page
    assert "/profiles/" not in page


def test_capture_analysis_page_is_get_only_and_linked_from_operator_console():
    # Newer FastAPI/Starlette versions can retain an internal _IncludedRouter
    # sentinel in app.routes. Only APIRoute-like entries expose .path/.methods.
    route = next(
        route
        for route in app.routes
        if getattr(route, "path", None) == "/capture-diagnostics"
    )

    assert route.methods == {"GET"}
    operator_page = index()
    assert "Analyze Capture" in operator_page
    assert "location.href='/capture-diagnostics'" in operator_page


def test_capture_analysis_console_keeps_live_session_diagnostics_separate():
    page = html()

    assert "Capture analysis is separate from the live session-state diagnostics stream." in page
    assert "/api/v1/interfaces/${encodeURIComponent(name)}/diagnostics" not in page
