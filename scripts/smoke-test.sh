#!/usr/bin/env bash
# Container smoke test: runs the image the way Kubernetes will and checks its parts are wired together.
# The app's rules are covered by pytest. Usage: scripts/smoke-test.sh <image>
set -euo pipefail

IMAGE="$1"
POSTGRES_IMAGE="docker.io/library/postgres:18.7-trixie@sha256:e754b839f447639b7004895f4d8a4bfcb4e9dbe3a1bc035f27f646562a16fd61"
POD="release-notes-it"
URL="http://127.0.0.1:18080"
DATABASE_URL="postgresql+psycopg://app:app@127.0.0.1:5432/app"
HARDENED=(--read-only --read-only-tmpfs=false --cap-drop ALL --security-opt no-new-privileges)

fail() {
    echo "FAIL: $1" >&2
    if podman container exists "$POD-app"; then
        podman logs "$POD-app" 2>&1 | tail -30 >&2
    fi
    exit 1
}

wait_for() {
    for _ in $(seq 1 30); do
        "$@" > /dev/null 2>&1 && return 0
        sleep 1
    done
    return 1
}

podman pod create --name "$POD" -p 127.0.0.1:18080:8080 > /dev/null
trap 'podman pod rm -f "$POD" > /dev/null' EXIT

echo "--- image runs as a non-root user by itself"
user=$(podman image inspect --format '{{.Config.User}}' "$IMAGE")
[ "$user" = "10001" ] || fail "image user is '$user', expected 10001"

echo "--- start Postgres"
podman run -d --pod "$POD" --name "$POD-db" \
    -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app -e POSTGRES_DB=app \
    "$POSTGRES_IMAGE" > /dev/null
wait_for podman exec "$POD-db" pg_isready -h 127.0.0.1 -U app -d app || fail "Postgres not ready"

echo "--- run migrations from the image"
podman run --rm --pod "$POD" "${HARDENED[@]}" -e DATABASE_URL="$DATABASE_URL" \
    "$IMAGE" alembic upgrade head || fail "migrations failed"

echo "--- start the app read-only, no capabilities"
podman run -d --pod "$POD" --name "$POD-app" "${HARDENED[@]}" -e DATABASE_URL="$DATABASE_URL" \
    "$IMAGE" > /dev/null
wait_for curl -fs "$URL/healthz/ready" || fail "app not ready"

echo "--- create a release and read it back"
id=$(curl -fsS -X POST "$URL/api/releases" -H 'Content-Type: application/json' \
    -d '{"version": "9.9.9", "description": "smoke test"}' | jq -r .id) || fail "create failed"
curl -fsS "$URL/api/releases/$id" | jq -e '.version == "9.9.9"' > /dev/null || fail "read back failed"

echo "--- UI page is served"
curl -fsS -o /dev/null "$URL/" || fail "UI page not served"

echo "--- stops cleanly on SIGTERM"
podman stop -t 25 "$POD-app" > /dev/null
code=$(podman inspect --format '{{.State.ExitCode}}' "$POD-app")
[ "$code" = "0" ] || fail "exit code $code after stop, expected 0"

echo "PASS"
