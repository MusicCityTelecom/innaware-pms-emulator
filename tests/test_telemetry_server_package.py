from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "deployment" / "telemetry"


def test_server_package_contains_public_ingest_and_protected_dashboard_example():
    ingest = (SERVER / "pms-telemetry-ingest.php").read_text(encoding="utf-8")
    apache = (SERVER / "apache-vhost.example.conf").read_text(encoding="utf-8")
    schema = (SERVER / "schema.sql").read_text(encoding="utf-8")

    assert "REQUEST_METHOD'] !== 'POST'" in ingest
    assert "application/json" in ingest
    assert "JSON_THROW_ON_ERROR" in ingest
    assert "ATTR_EMULATE_PREPARES => false" in ingest
    assert "INSERT IGNORE INTO telemetry_events" in ingest
    assert "Require all granted" in apache
    assert '<Files "pms-telemetry.php">' in apache
    assert "Require valid-user" in apache
    assert "UNIQUE KEY uq_install_event" in schema


def test_server_does_not_store_network_or_identity_fields():
    schema = (SERVER / "schema.sql").read_text(encoding="utf-8").lower()
    forbidden = ("ip_address", "user_agent", "hostname", "username", "email", "mac_address")
    assert all(field not in schema for field in forbidden)
