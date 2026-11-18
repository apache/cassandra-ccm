#!/usr/bin/env bash
#
# Stress-test the socket-release fix (f53daac) by repeatedly stopping and
# starting a single-node ccm cluster and watching for "Inet address ...
# is not available" failures.
#
# Usage: ./stop_start_loop.sh [version] [iterations]
#   version:    Cassandra version to install, e.g. 5.0.2 or git:trunk (default: 5.0.2)
#   iterations: number of stop/start cycles to run (default: 50)

set -uo pipefail

VERSION="${1:-5.0.2}"
ITERATIONS="${2:-50}"
CLUSTER_NAME="stoploop"

CCM="$(cd "$(dirname "$0")" && pwd)/ccm"

cleanup() {
  "$CCM" remove "$CLUSTER_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# echo "Removing any stale cluster named '$CLUSTER_NAME'..."
# "$CCM" remove "$CLUSTER_NAME" >/dev/null 2>&1 || true

# echo "Creating single-node cluster '$CLUSTER_NAME' (version=$VERSION)..."
# "$CCM" create "$CLUSTER_NAME" -v "$VERSION" -n1 --vnodes --quiet

echo "Starting cluster for the first time..."
if ! "$CCM" start; then
  echo "FAIL: initial start failed"
  exit 1
fi

fail_count=0
for i in $(seq 1 "$ITERATIONS"); do
  start_ts=$(date +%s)

  if ! "$CCM" stop; then
    echo "FAIL on iteration $i: stop failed"
    fail_count=$((fail_count + 1))
    break
  fi

  if ! "$CCM" start; then
    echo "FAIL on iteration $i: start failed (likely socket-still-bound race)"
    fail_count=$((fail_count + 1))
    break
  fi

  elapsed=$(( $(date +%s) - start_ts ))
  echo "iteration $i/$ITERATIONS OK (${elapsed}s)"
done

"$CCM" stop >/dev/null 2>&1 || true

if [ "$fail_count" -eq 0 ]; then
  echo "All $ITERATIONS stop/start cycles succeeded."
  exit 0
else
  echo "Stopped after failure on iteration $i. See ccm node logs for details."
  exit 1
fi
