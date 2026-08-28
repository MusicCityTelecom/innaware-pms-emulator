from innaware_pms_emulator.operator_console import html


def test_guest_operations_support_direct_debug_without_property():
    page = html()
    assert "Property mode is optional" in page
    assert "/send/guest-event" in page
    assert "Select a PMS interface for direct debug mode." in page
