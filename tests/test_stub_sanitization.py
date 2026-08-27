from pathlib import Path


# Real names and organization/vendor names previously seen in historical test
# material. Mitel is intentionally excluded because it is the compatibility
# profile identifier for these synthetic fixtures.
FORBIDDEN_STUB_TOKENS = {
    "HEGGIE",
    "TOMMY",
    "ROBERT",
    "SMITH",
    "JOHN",
    "OPENAI",
    "CHATGPT",
    "TECHFINITY",
    "PHONESUITE",
    "VOICEWARE",
    "MUSICCITYTELECOM",
    "MUSIC CITY TELECOM",
    "HILTON",
    "ORACLE",
    "MICROS",
    "3CX",
    "TELELECTRONICS",
    "CHOICE",
    "OPERA",
}


def test_protocol_stubs_are_sanitized():
    stub_dir = Path(__file__).resolve().parents[1] / "stubs"
    assert stub_dir.is_dir()
    stubs = list(stub_dir.glob("*.json"))
    assert stubs
    for path in stubs:
        text = path.read_text(encoding="utf-8").upper()
        for token in FORBIDDEN_STUB_TOKENS:
            assert token not in text, f"unsanitized token {token!r} found in {path.name}"
