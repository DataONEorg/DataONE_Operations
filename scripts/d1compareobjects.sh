#!/usr/bin/env bash
#
# Bash port of scripts/d1compareobjects.
#
# Compare the objects held by a Member Node with the objects known to a
# Coordinating Node, and report identifiers that are present on the MN but
# have not yet been synchronized to the CN.
#
# Requires: curl, xmlstarlet
#
# Authentication is via a Bearer token. Set the TOKEN_FILE environment
# variable to the path of a file containing the token string.
#
# Requires a member node token file at ~/force_sync/token/NODE, where NODE is the nodeId of the MN.
#
# Usage:
#   d1compareobjects.sh [options] <mn_id>
#
# Options:
#   --env ENV            Environment: dev, stage, sandbox, prod (default: prod)
#   --mn-base-url URL    Base URL of the MN (looked up from the CN if omitted)
#   -o, --out FILE       File to write unsynced identifiers to (default: stdout)
#   -f, --force-sync     Invoke a force sync for each unsynchronized identifier
#   --debug              Verbose logging to stderr

set -euo pipefail

PAGE_SIZE=1000

declare -A ENV_BASE_URL=(
  [dev]="https://cn-dev.test.dataone.org/cn"
  [stage]="https://cn-stage.test.dataone.org/cn"
  [sandbox]="https://cn-sandbox.test.dataone.org/cn"
  [prod]="https://cn.dataone.org/cn"
)

ENV_NAME="prod"
MN_ID=""
MN_BASE_URL=""
OUT_PATH=""
TOKEN_FILE=""
FORCE_SYNC=0
DEBUG=0

log() {
  # info-level logging to stderr, always shown
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO     $*" >&2
}

debug() {
  [[ "$DEBUG" -eq 1 ]] && echo "$(date '+%Y-%m-%d %H:%M:%S') DEBUG    $*" >&2
  return 0
}

usage() {
  grep '^#' "$0" | sed -e 's/^#//' -e 's/^ //'
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV_NAME="$2"; shift 2 ;;
    --mn-base-url) MN_BASE_URL="$2"; shift 2 ;;
    -o|--out) OUT_PATH="$2"; shift 2 ;;
    -f|--force-sync) FORCE_SYNC=1; shift ;;
    --debug) DEBUG=1; shift ;;
    -h|--help) usage ;;
    -*) echo "Unknown option: $1" >&2; usage ;;
    *) MN_ID="$1"; shift ;;
  esac
done

if [[ -z "$MN_ID" ]]; then
  echo "Error: mn_id is required" >&2
  usage
fi

for tool in curl xmlstarlet; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "Error: required tool '$tool' not found in PATH" >&2
    exit 1
  }
done

CN_BASE_URL="${ENV_BASE_URL[$ENV_NAME]:-}"
if [[ -z "$CN_BASE_URL" ]]; then
  echo "Error: environment must be one of: ${!ENV_BASE_URL[*]}" >&2
  exit 1
fi

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT
OUTDIR=$(~/force_sync/)
mkdir -p "$OUTDIR/token" "$OUTDIR/pid"
MN_NAME=${$MN_ID##*:}
TOKEN_FILE="$OUTDIR/token/${MN_NAME}"

if [[ -z "${TOKEN_FILE:-}" ]]; then
  echo "Error: TOKEN_FILE environment variable must point to a file containing the auth token" >&2
  exit 1
fi
if [[ ! -r "$TOKEN_FILE" ]]; then
  echo "Error: TOKEN_FILE '$TOKEN_FILE' does not exist or is not readable" >&2
  exit 1
fi
TOKEN=$(<"$TOKEN_FILE")
TOKEN="${TOKEN//$'\n'/}"
if [[ -z "$TOKEN" ]]; then
  echo "Error: TOKEN_FILE '$TOKEN_FILE' is empty" >&2
  exit 1
fi

CURL_OPTS=(-s -S -f -H "Authorization: Bearer ${TOKEN}")

# xpath helpers use local-name() so the CN/MN response namespace (v1 or v2) doesn't matter.
xml_field() {
  # xml_field FILE XPATH -> prints matched text node value(s), one per line
  xmlstarlet sel -t -m "$2" -v "." -n "$1" 2>/dev/null || true
}

resolve_mn_base_url() {
  local node_list_file="$WORKDIR/nodelist.xml"
  log "Looking up base URL for $MN_ID from CN node list"
  curl "${CURL_OPTS[@]}" "$CN_BASE_URL/v2/node" -o "$node_list_file"
  local url
  url=$(xml_field "$node_list_file" \
    "//*[local-name()='node'][*[local-name()='identifier']='$MN_ID']/*[local-name()='baseURL']")
  if [[ -z "$url" ]]; then
    echo "Error: NodeId '$MN_ID' not found in CN node list and --mn-base-url not provided" >&2
    exit 1
  fi
  echo "$url"
}

# get_all_pids BASE_URL EXTRA_QUERY OUT_FILE
get_all_pids() {
  local base_url="$1"
  local extra_query="$2"
  local out_file="$3"
  : > "$out_file"

  local start=0
  local total=-1
  local page=0

  while [[ "$total" -lt 0 || "$start" -lt "$total" ]]; do
    page=$((page + 1))
    local resp_file="$WORKDIR/page_${RANDOM}_${page}.xml"
    local url="${base_url}/v2/object?start=${start}&count=${PAGE_SIZE}${extra_query}"
    debug "GET $url"
    if ! curl "${CURL_OPTS[@]}" "$url" -o "$resp_file"; then
      log "listObjects request failed for $url"
      break
    fi

    if [[ "$total" -lt 0 ]]; then
      total=$(xml_field "$resp_file" "//*[local-name()='total']")
      [[ -z "$total" ]] && total=0
      log "Total matching records = $total"
    fi

    local count
    count=$(xml_field "$resp_file" "//*[local-name()='count']")
    [[ -z "$count" ]] && count=0

    xml_field "$resp_file" "//*[local-name()='objectInfo']/*[local-name()='identifier']" >> "$out_file"

    if [[ "$count" -eq 0 ]]; then
      break
    fi
    start=$((start + count))
  done
}

if [[ -z "$MN_BASE_URL" ]]; then
  MN_BASE_URL=$(resolve_mn_base_url)
fi
log "MN base URL = $MN_BASE_URL"

MN_PIDS_FILE="$WORKDIR/$($MN_NAME)_mn_pids.txt"
CN_PIDS_FILE="$WORKDIR/$($MN_NAME)_cn_pids.txt"

log "Retrieving identifiers from MN $MN_ID ($MN_BASE_URL)"
get_all_pids "$MN_BASE_URL" "" "$MN_PIDS_FILE"
log "MN has $(wc -l < "$MN_PIDS_FILE" | tr -d ' ') identifiers"

log "Retrieving identifiers known to CN for nodeId=$MN_ID"
get_all_pids "$CN_BASE_URL" "&nodeId=$MN_ID" "$CN_PIDS_FILE"
log "CN has $(wc -l < "$CN_PIDS_FILE" | tr -d ' ') identifiers for this MN"

UNSYNCED_FILE="$OUTDIR/$MN_NAME"
NUM_UNSYNCED=$(wc -l < "$UNSYNCED_FILE" | tr -d ' ')
comm -23 <(sort -u "$MN_PIDS_FILE") <(sort -u "$CN_PIDS_FILE") > "$UNSYNCED_FILE"
log "$NUM_UNSYNCED identifiers on MN are not yet on CN"

if [[ -n "$OUT_PATH" ]]; then
  cp "$UNSYNCED_FILE" "$OUT_PATH"
else
  cat "$UNSYNCED_FILE"
fi

if [[ "${FORCE_SYNC:-0}" -eq 1 ]]; then
  log "Force sync invoked for $MN_NAME. Start time: $(date '+%Y-%m-%d %H:%M:%S')"
  log "This action enforces a wait time of 5 seconds between each request to avoid overwhelming the CN. This could take a long time ($((NUM_UNSYNCED * 5)) seconds)."
  debug "Force sync attempted for the following identifiers:"
  while read line; do
    debug "$line"
    curl -H "Authorization: Bearer ${TOKEN}" -F "pid=$line" -X POST https://cn.dataone.org/cn/v2/synchronize || true
    sleep 5
  done < "$UNSYNCED_FILE"
  log "Force sync completed for $MN_NAME"
  log "End time: $(date '+%Y-%m-%d %H:%M:%S')"
fi
