#!/bin/bash
set +e
set +u
set +o pipefail 2>/dev/null || true

REPO="${INNAWARE_PMS_REPO_DIR:-/opt/innaware/innaware-pms-emulator}"
PORT="${INNAWARE_PMS_VERIFY_PORT:-18080}"
TMP_DATA="$(mktemp -d /tmp/innaware-pms-verify.XXXXXX)"
LOG="$(mktemp /tmp/innaware-pms-verify.XXXXXX.log)"
PID=""

cleanup() {
    if [ -n "$PID" ]; then
        kill "$PID" 2>/dev/null || true
        wait "$PID" 2>/dev/null || true
    fi
    rm -rf "$TMP_DATA" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

cd "$REPO" || exit 1

printf '%s\n' "============================================================"
printf '%s\n' " INNAWARE PMS EMULATOR 0.2.0 - SERVER3 VERIFICATION"
printf '%s\n' "============================================================"
printf '%s\n' "# Diagnostic/test run only."
printf '%s\n' "# Uses an isolated temporary data directory."
printf '%s\n' "# Does not touch configured PMS/CA interfaces."
printf '%s\n' "# Does not reboot the host."
printf '\n'

printf '%s\n' "===== GIT ====="
git fetch origin main
fetch_rc=$?
printf 'fetch rc=%s\n' "$fetch_rc"
printf 'HEAD:   %s\n' "$(git rev-parse --short HEAD 2>/dev/null)"
printf 'REMOTE: %s\n' "$(git rev-parse --short origin/main 2>/dev/null)"
git status --short
git diff --check
diff_rc=$?
printf 'diff check rc=%s\n\n' "$diff_rc"

printf '%s\n' "===== PYTHON / PACKAGE ====="
if [ ! -x .venv/bin/python ]; then
    printf '%s\n' "ERROR: .venv/bin/python is missing."
    package_rc=90
else
    .venv/bin/python --version
    .venv/bin/python -c 'import innaware_pms_emulator; print("version:", innaware_pms_emulator.__version__)'
    package_rc=$?
fi
printf 'package import rc=%s\n\n' "$package_rc"

printf '%s\n' "===== COMPILE ====="
.venv/bin/python -m compileall -q src tests
compile_rc=$?
printf 'compile rc=%s\n\n' "$compile_rc"

printf '%s\n' "===== PYTEST ====="
.venv/bin/python -m pytest -q
test_rc=$?
printf 'pytest rc=%s\n\n' "$test_rc"

printf '%s\n' "===== ISOLATED API SMOKE TEST ====="
export INNAWARE_PMS_DATA_DIR="$TMP_DATA"
.venv/bin/python -m uvicorn \
    innaware_pms_emulator.main:app \
    --app-dir src \
    --host 127.0.0.1 \
    --port "$PORT" \
    >"$LOG" 2>&1 &
PID=$!

api_ready=0
for _ in $(seq 1 50); do
    if curl -fsS "http://127.0.0.1:${PORT}/api/v1/health" >/dev/null 2>&1; then
        api_ready=1
        break
    fi
    sleep 0.1
done

if [ "$api_ready" -ne 1 ]; then
    printf '%s\n' "ERROR: isolated API did not become ready."
    tail -n 100 "$LOG"
    api_rc=91
else
    printf '%s\n' "--- health ---"
    curl -fsS "http://127.0.0.1:${PORT}/api/v1/health" | .venv/bin/python -m json.tool
    health_rc=$?

    printf '%s\n' "--- protocol catalog ---"
    curl -fsS "http://127.0.0.1:${PORT}/api/v1/protocols" | .venv/bin/python -m json.tool
    protocols_rc=$?

    printf '%s\n' "--- seed demo property ---"
    curl -fsS -X POST \
        "http://127.0.0.1:${PORT}/api/v1/scenarios/small-hotel?property_id=verify-hotel" \
        >/tmp/innaware-pms-verify-property.json
    seed_rc=$?
    if [ "$seed_rc" -eq 0 ]; then
        .venv/bin/python - <<'PY'
import json
p = json.load(open('/tmp/innaware-pms-verify-property.json'))
print('property:', p['id'], p['name'])
print('rooms:', len(p['rooms']))
print('active stays:', sum(1 for x in p['stays'].values() if x['status'] == 'active'))
print('scheduled wakeups:', sum(1 for x in p['wakeups'].values() if x['status'] == 'scheduled'))
assert len(p['rooms']) == 30
assert p['rooms']['101']['active_stay_id'] == 'stay-demo-1'
assert p['rooms']['103']['active_stay_id'] == 'stay-demo-2'
assert p['rooms']['102']['housekeeping'] == 'dirty'
PY
        seed_assert_rc=$?
    else
        seed_assert_rc=92
    fi

    printf '%s\n' "--- property-bound disabled FIAS interface ---"
    curl -fsS -X POST \
        "http://127.0.0.1:${PORT}/api/v1/interfaces" \
        -H 'Content-Type: application/json' \
        -d '{"name":"verify-fias","purpose":"pms","protocol":"FIAS","transport":"tcp_server","property_id":"verify-hotel","enabled":false,"bind_host":"127.0.0.1","port":19001,"options":{"framing":"crlf","role":"pms"}}' \
        | .venv/bin/python -m json.tool
    interface_rc=$?

    printf '%s\n' "--- Hilton combined name fixture ---"
    curl -fsS -X POST \
        "http://127.0.0.1:${PORT}/api/v1/protocols/HILTON_PEP_FIAS/guest-event" \
        -H 'Content-Type: application/json' \
        -d '{"action":"checkin","room":"101","last_name":"Smith","first_name":"John"}' \
        >/tmp/innaware-pms-verify-hilton.json
    hilton_rc=$?
    if [ "$hilton_rc" -eq 0 ]; then
        .venv/bin/python - <<'PY'
import json
p = json.load(open('/tmp/innaware-pms-verify-hilton.json'))
print(p['text'].rstrip())
assert p['text'] == 'GI|RN101|GNSmith, John|\r\n'
assert 'GFJohn' not in p['text']
PY
        hilton_assert_rc=$?
    else
        hilton_assert_rc=93
    fi

    if [ "$health_rc" -eq 0 ] && \
       [ "$protocols_rc" -eq 0 ] && \
       [ "$seed_rc" -eq 0 ] && \
       [ "$seed_assert_rc" -eq 0 ] && \
       [ "$interface_rc" -eq 0 ] && \
       [ "$hilton_rc" -eq 0 ] && \
       [ "$hilton_assert_rc" -eq 0 ]; then
        api_rc=0
    else
        api_rc=94
    fi
fi
printf 'API smoke rc=%s\n\n' "$api_rc"

rm -f /tmp/innaware-pms-verify-property.json /tmp/innaware-pms-verify-hilton.json

printf '%s\n' "===== SOURCE ARCHIVE ====="
SOURCE_ZIP="/tmp/InnAware-PMS-Emulator-Source-$(git rev-parse --short HEAD).zip"
git archive --format=zip --output="$SOURCE_ZIP" HEAD
archive_rc=$?
printf 'source archive rc=%s\n' "$archive_rc"
if [ "$archive_rc" -eq 0 ]; then
    ls -lh "$SOURCE_ZIP"
    sha256sum "$SOURCE_ZIP"
fi
printf '\n'

printf '%s\n' "===== FINAL ====="
printf 'fetch=%s diff=%s package=%s compile=%s pytest=%s api=%s archive=%s\n' \
    "$fetch_rc" "$diff_rc" "$package_rc" "$compile_rc" "$test_rc" "$api_rc" "$archive_rc"
printf 'uvicorn log: %s\n' "$LOG"

if [ "$diff_rc" -eq 0 ] && \
   [ "$package_rc" -eq 0 ] && \
   [ "$compile_rc" -eq 0 ] && \
   [ "$test_rc" -eq 0 ] && \
   [ "$api_rc" -eq 0 ] && \
   [ "$archive_rc" -eq 0 ]; then
    printf '%s\n' "RESULT=PASS"
    exit 0
fi

printf '%s\n' "RESULT=FAIL"
exit 1
