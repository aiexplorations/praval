#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
collector_image="${PRAVAL_OTEL_COLLECTOR_IMAGE:-otel/opentelemetry-collector-contrib:0.113.0}"
container_name="praval-o5-collector-$$"
output_dir="$(mktemp -d "${TMPDIR:-/tmp}/praval-o5-collector.XXXXXX")"

cleanup() {
    docker stop "${container_name}" >/dev/null 2>&1 || true
    docker rm "${container_name}" >/dev/null 2>&1 || true
    case "${output_dir}" in
        */praval-o5-collector.*) find "${output_dir}" -depth -delete ;;
    esac
}
trap cleanup EXIT

docker run \
    --name "${container_name}" \
    --user 0 \
    -d \
    -p 127.0.0.1::4317 \
    -p 127.0.0.1::4318 \
    -v "${repository_dir}/tests/integration/fixtures/otel-collector-config.yaml:/etc/otelcol-contrib/config.yaml:ro" \
    -v "${output_dir}:/output" \
    "${collector_image}" \
    --config=/etc/otelcol-contrib/config.yaml >/dev/null

for _ in $(seq 1 30); do
    if docker logs "${container_name}" 2>&1 | rg -q "Everything is ready"; then
        break
    fi
    sleep 0.2
done

if ! docker logs "${container_name}" 2>&1 | rg -q "Everything is ready"; then
    docker logs "${container_name}"
    exit 1
fi

grpc_address="$(docker port "${container_name}" 4317/tcp)"
http_address="$(docker port "${container_name}" 4318/tcp)"
grpc_port="${grpc_address##*:}"
http_port="${http_address##*:}"

PRAVAL_TEST_OTLP_OUTPUT_DIR="${output_dir}" \
PRAVAL_TEST_OTLP_HTTP_ENDPOINT="http://127.0.0.1:${http_port}" \
PRAVAL_TEST_OTLP_GRPC_ENDPOINT="127.0.0.1:${grpc_port}" \
    "${repository_dir}/venv/bin/python" -m pytest \
    "${repository_dir}/tests/integration/test_otel_collector.py" -v
