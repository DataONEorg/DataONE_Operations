#!/usr/bin/env bash
##
# Walk the version chain of a single PID (or SID) forwards and backwards on
# the Member Node and on the CN, report every place where the CN's chain links
# differ from the MN's, and try to repair them.
#
# The MN is treated as the source of truth. For each PID in the MN chain the
# CN system metadata is compared with the MN's: the PID must exist on the CN
# and its obsoletes, obsoletedBy and seriesId must match. Repair is attempted
# in increasing order of forcefulness:
#
#   1. Re-synchronize the broken PID with POST /v2/synchronize and poll the CN
#      /meta endpoint until the links match (or --wait seconds pass).
#   2. With --fix-db, if the CN still disagrees, set obsoletes / obsoleted_by /
#      series_id in the metacat systemmetadata table to the MN's values
#      (a dry run that only prints the SQL unless --execute is also given).
#      This must run on a CN with sudo/postgres access, and on both CNs.
#      PIDs that have no systemmetadata row at all cannot be fixed this way;
#      they are reported for cn_force_accounting.sh.
#
# Requires: curl, xmlstarlet (and psql + sudo for --fix-db)
#
# Requires a member node token file at ~/force_sync/token/NODE, where NODE is
# the shortened nodeId of the MN (i.e. UCSB1 for urn:node:UCSB1).
#
# Usage:
#   d1cn_repair_chain.sh [options] <mn_id> <pid_or_sid>
#
# Options:
#   --env ENV            Environment: dev, stage, sandbox, prod (default: prod)
#   --mn-base-url URL    Base URL of the MN (looked up from the CN if omitted)
#   --cn-base-url URL    Override the CN base URL derived from --env
#   --no-sync            Only report; do not re-synchronize
#   --wait SECONDS       How long to poll the CN after each sync (default: 60)
#   --fix-db             If sync does not fix a link, correct the CN
#                        systemmetadata table directly (dry run unless --execute)
#   --execute            With --fix-db, actually run the UPDATE statements
#   --debug              Verbose logging to stderr
#   -h, --help           Show this help message and exit
#
# Exit status is 0 if the CN chain matches the MN chain at the end, 1 if
# broken links remain, 2 on a usage or lookup error.
#
# WARNING: --fix-db --execute modifies postgres directly, bypassing the API.
# Back up the metacat database first.

set -euo pipefail

declare -A ENV_BASE_URL=(
  [dev]="https://cn-dev.test.dataone.org/cn"
  [stage]="https://cn-stage.test.dataone.org/cn"
  [sandbox]="https://cn-sandbox.test.dataone.org/cn"
  [prod]="https://cn.dataone.org/cn"
)

ENV_NAME="prod"
MN_ID=""
INPUT_ID=""
MN_BASE_URL=""
CN_BASE_OVERRIDE=""
DO_SYNC=1
WAIT_SECS=60
POLL_SECS=10
FIX_DB=0
EXECUTE=0
DEBUG=0

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') INFO     $*" >&2; }
debug() { [[ "$DEBUG" -eq 1 ]] && echo "$(date '+%Y-%m-%d %H:%M:%S') DEBUG    $*" >&2; return 0; }
usage() { grep '^#' "$0" | sed -e 's/^#//' -e 's/^ //'; exit 2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV_NAME="$2"; shift 2 ;;
    --mn-base-url) MN_BASE_URL="${2%/}"; shift 2 ;;
    --cn-base-url) CN_BASE_OVERRIDE="${2%/}"; shift 2 ;;
    --no-sync) DO_SYNC=0; shift ;;
    --wait) WAIT_SECS="$2"; shift 2 ;;
    --fix-db) FIX_DB=1; shift ;;
    --execute) EXECUTE=1; shift ;;
    --debug) DEBUG=1; shift ;;
    -h|--help) usage ;;
    -*) echo "Unknown option: $1" >&2; usage ;;
    *)
      if [[ -z "$MN_ID" ]]; then MN_ID="$1"
      elif [[ -z "$INPUT_ID" ]]; then INPUT_ID="$1"
      else echo "Unexpected argument: $1" >&2; usage; fi
      shift ;;
  esac
done

[[ -n "$MN_ID" && -n "$INPUT_ID" ]] || { echo "Error: mn_id and pid_or_sid are required" >&2; usage; }
[[ "$WAIT_SECS" =~ ^[0-9]+$ ]] || { echo "Error: --wait must be a non-negative integer" >&2; exit 2; }
[[ "$EXECUTE" -eq 0 || "$FIX_DB" -eq 1 ]] || { echo "Error: --execute requires --fix-db" >&2; exit 2; }

REQUIRED=(curl xmlstarlet)
[[ "$FIX_DB" -eq 1 && "$EXECUTE" -eq 1 ]] && REQUIRED+=(psql sudo)
for tool in "${REQUIRED[@]}"; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Error: required tool '$tool' not found in PATH" >&2; exit 2; }
done

CN_BASE_URL="${CN_BASE_OVERRIDE:-${ENV_BASE_URL[$ENV_NAME]:-}}"
[[ -n "$CN_BASE_URL" ]] || { echo "Error: environment must be one of: ${!ENV_BASE_URL[*]}" >&2; exit 2; }

MN_NAME=${MN_ID##*:}
TOKEN_FILE="$HOME/force_sync/token/${MN_NAME}"
[[ -r "$TOKEN_FILE" ]] || { echo "Error: TOKEN_FILE '$TOKEN_FILE' does not exist or is not readable" >&2; exit 2; }
TOKEN=$(tr -d '\r\n' < "$TOKEN_FILE")
[[ -n "$TOKEN" ]] || { echo "Error: TOKEN_FILE '$TOKEN_FILE' is empty" >&2; exit 2; }

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

urlencode() {
  local LC_ALL=C s="$1" i c out=""
  for ((i = 0; i < ${#s}; i++)); do
    c="${s:i:1}"
    case "$c" in
      [A-Za-z0-9.~_-]) out+="$c" ;;
      *) printf -v c '%%%02X' "'$c"; out+="$c" ;;
    esac
  done
  printf '%s' "$out"
}

sql_quote() {
  local v="${1:-}"
  if [[ -z "$v" ]]; then printf 'NULL'; return; fi
  v=${v//\\/\\\\}
  v=${v//"'"/"''"}
  printf "'%s'" "$v"
}

db_exec() { sudo -u postgres psql -d metacat -v ON_ERROR_STOP=1 -At -c "$1"; }

if [[ -z "$MN_BASE_URL" ]]; then
  log "Looking up base URL for $MN_ID from the CN node list"
  curl -sSf -H "Authorization: Bearer ${TOKEN}" "$CN_BASE_URL/v2/node" -o "$WORKDIR/nodes.xml"
  MN_BASE_URL=$(xmlstarlet sel -t -m "//*[local-name()='node'][*[local-name()='identifier']='$MN_ID']/*[local-name()='baseURL']" \
    -v . -n "$WORKDIR/nodes.xml" 2>/dev/null | head -n 1 || true)
  MN_BASE_URL="${MN_BASE_URL%/}"
  [[ -n "$MN_BASE_URL" ]] || { echo "Error: $MN_ID not found in CN node list; use --mn-base-url" >&2; exit 2; }
fi
log "MN base URL = $MN_BASE_URL"
log "CN base URL = $CN_BASE_URL"

# Metadata cache keyed by "side|pid" where side is mn or cn.
# STATE: ok|missing|error. Other fields hold the sysmeta values.
declare -A STATE IDENT OBSOLETES OBSOLETED_BY SERIES

base_url() { [[ "$1" == mn ]] && echo "$MN_BASE_URL" || echo "$CN_BASE_URL"; }

# fetch_meta SIDE ID [force]: populates the cache; ID may be a PID or SID.
fetch_meta() {
  local side="$1" id="$2" force="${3:-}" key="$1|$2"
  [[ -z "$force" && -n "${STATE[$key]:-}" ]] && return 0
  local f="$WORKDIR/meta.xml" code
  code=$(curl -sS -o "$f" -w '%{http_code}' -H "Authorization: Bearer ${TOKEN}" \
    "$(base_url "$side")/v2/meta/$(urlencode "$id")" 2>/dev/null || true)
  case "$code" in
    200)
      STATE[$key]=ok
      local q="//*[local-name()='systemMetadata']/*[local-name()='%s']"
      IDENT[$key]=$(xmlstarlet sel -t -v "$(printf "$q" identifier)" "$f" 2>/dev/null || true)
      OBSOLETES[$key]=$(xmlstarlet sel -t -v "$(printf "$q" obsoletes)" "$f" 2>/dev/null || true)
      OBSOLETED_BY[$key]=$(xmlstarlet sel -t -v "$(printf "$q" obsoletedBy)" "$f" 2>/dev/null || true)
      SERIES[$key]=$(xmlstarlet sel -t -v "$(printf "$q" seriesId)" "$f" 2>/dev/null || true)
      ;;
    404) STATE[$key]=missing ;;
    *) STATE[$key]=error; log "Unexpected HTTP status '$code' fetching $side sysmeta for $id" ;;
  esac
  debug "$side meta $id -> ${STATE[$key]}"
}

# Resolve the input to a PID. A SID resolves to the head of its chain.
START_PID=""
for side in mn cn; do
  fetch_meta "$side" "$INPUT_ID"
  if [[ "${STATE[$side|$INPUT_ID]}" == ok && -n "${IDENT[$side|$INPUT_ID]}" ]]; then
    START_PID="${IDENT[$side|$INPUT_ID]}"
    [[ "$START_PID" != "$INPUT_ID" ]] && log "$INPUT_ID is a SID; resolved on $side to head PID $START_PID"
    break
  fi
done
[[ -n "$START_PID" ]] || { echo "Error: '$INPUT_ID' not found as a PID or SID on the MN or the CN" >&2; exit 2; }
# SID lookups return the head sysmeta under the SID key; cache it under the PID too.
fetch_meta mn "$START_PID"
fetch_meta cn "$START_PID"

REPORT="$HOME/force_sync/pid/${MN_NAME}.walk.report"
mkdir -p "$(dirname "$REPORT")"
: > "$REPORT"

# Walk the MN chain: CHAIN is ordered oldest -> newest. Ends are noted when
# the MN itself cannot supply a neighbour.
declare -A IN_CHAIN
BACK=() FWD=()
IN_CHAIN[$START_PID]=1

if [[ "${STATE[mn|$START_PID]}" != ok ]]; then
  log "WARNING: $START_PID is not available on the MN (${STATE[mn|$START_PID]}); walking from the CN's copy"
  WALK_SIDE=cn
else
  WALK_SIDE=mn
fi

cur="$START_PID"
while :; do
  prev="${OBSOLETES[$WALK_SIDE|$cur]:-}"
  [[ -n "$prev" ]] || break
  [[ -z "${IN_CHAIN[$prev]:-}" ]] || { log "Cycle detected at $prev (backwards)"; break; }
  IN_CHAIN[$prev]=1; BACK=("$prev" ${BACK[@]+"${BACK[@]}"})
  fetch_meta mn "$prev"
  fetch_meta cn "$prev"
  if [[ "${STATE[mn|$prev]}" == ok ]]; then WALK_SIDE=mn
  elif [[ "${STATE[cn|$prev]}" == ok ]]; then WALK_SIDE=cn
  else log "Backward walk ends: $prev is unavailable on both MN and CN"; break; fi
  cur="$prev"
done

[[ "${STATE[mn|$START_PID]}" == ok ]] && WALK_SIDE=mn || WALK_SIDE=cn
cur="$START_PID"
while :; do
  next="${OBSOLETED_BY[$WALK_SIDE|$cur]:-}"
  [[ -n "$next" ]] || break
  [[ -z "${IN_CHAIN[$next]:-}" ]] || { log "Cycle detected at $next (forwards)"; break; }
  IN_CHAIN[$next]=1; FWD+=("$next")
  fetch_meta mn "$next"
  fetch_meta cn "$next"
  if [[ "${STATE[mn|$next]}" == ok ]]; then WALK_SIDE=mn
  elif [[ "${STATE[cn|$next]}" == ok ]]; then WALK_SIDE=cn
  else log "Forward walk ends: $next is unavailable on both MN and CN"; break; fi
  cur="$next"
done

CHAIN=(${BACK[@]+"${BACK[@]}"} "$START_PID" ${FWD[@]+"${FWD[@]}"})
log "Chain has ${#CHAIN[@]} link(s): ${#BACK[@]} before and ${#FWD[@]} after $START_PID"

# check_pid PID: prints a reason string if the CN differs from the MN, else nothing.
check_pid() {
  local pid="$1" m="mn|$1" c="cn|$1" issues=()
  case "${STATE[$c]}" in
    missing) echo "missing on CN"; return ;;
    error) echo "CN lookup error"; return ;;
  esac
  if [[ "${STATE[$m]}" == missing ]]; then
    # Not on the MN (e.g. deleted): nothing authoritative to compare with.
    return
  fi
  [[ "${STATE[$m]}" == ok ]] || return
  [[ "${OBSOLETES[$m]}" == "${OBSOLETES[$c]}" ]] || issues+=("obsoletes MN='${OBSOLETES[$m]}' CN='${OBSOLETES[$c]}'")
  [[ "${OBSOLETED_BY[$m]}" == "${OBSOLETED_BY[$c]}" ]] || issues+=("obsoletedBy MN='${OBSOLETED_BY[$m]}' CN='${OBSOLETED_BY[$c]}'")
  [[ "${SERIES[$m]}" == "${SERIES[$c]}" ]] || issues+=("seriesId MN='${SERIES[$m]}' CN='${SERIES[$c]}'")
  local IFS=';'
  [[ ${#issues[@]} -eq 0 ]] || echo "${issues[*]}"
}

print_chain() {
  local pid reason mark
  printf '\n%-4s %-6s %s\n' "#" "status" "pid"
  local i=0
  for pid in "${CHAIN[@]}"; do
    i=$((i + 1))
    reason=$(check_pid "$pid")
    mark="OK"; [[ -n "$reason" ]] && mark="BROKEN"
    [[ "$pid" == "$START_PID" ]] && pid="$pid  <-- start"
    printf '%-4s %-6s %s%s\n' "$i" "$mark" "$pid" "${reason:+   ($reason)}" >&2
  done
  echo >&2
}

declare -A BROKEN_REASON
collect_broken() {
  BROKEN_LIST=()
  local pid reason
  for pid in "${CHAIN[@]}"; do
    reason=$(check_pid "$pid")
    if [[ -n "$reason" ]]; then BROKEN_LIST+=("$pid"); BROKEN_REASON[$pid]="$reason"
    else unset 'BROKEN_REASON[$pid]'; fi
  done
}

collect_broken
log "Initial chain state (MN is the reference):"
print_chain
if [[ ${#BROKEN_LIST[@]} -eq 0 ]]; then
  log "CN chain matches the MN chain; nothing to fix"
  exit 0
fi
for pid in "${BROKEN_LIST[@]}"; do
  printf '%s\t%s\n' "$pid" "${BROKEN_REASON[$pid]}" >> "$REPORT"
done
log "${#BROKEN_LIST[@]} broken link(s) recorded in $REPORT"

refetch_cn() { fetch_meta cn "$1" force; }

# wait_for_match PID: poll the CN until PID matches the MN or time runs out.
wait_for_match() {
  local pid="$1" waited=0
  while :; do
    refetch_cn "$pid"
    [[ -z "$(check_pid "$pid")" ]] && return 0
    (( waited >= WAIT_SECS )) && return 1
    sleep "$POLL_SECS"; waited=$((waited + POLL_SECS))
  done
}

if [[ "$DO_SYNC" -eq 1 ]]; then
  for pid in "${BROKEN_LIST[@]}"; do
    log "Re-synchronizing $pid (${BROKEN_REASON[$pid]})"
    code=$(curl -sS -o /dev/null -w '%{http_code}' -H "Authorization: Bearer ${TOKEN}" \
      -F "pid=$pid" -X POST "$CN_BASE_URL/v2/synchronize" 2>/dev/null || true)
    debug "synchronize $pid -> HTTP $code"
    [[ "$code" == 2* ]] || log "synchronize request for $pid returned HTTP '$code'"
  done
  for pid in "${BROKEN_LIST[@]}"; do
    if wait_for_match "$pid"; then log "Fixed by synchronization: $pid"
    else log "Still broken after ${WAIT_SECS}s: $pid"; fi
  done
  collect_broken
fi

if [[ ${#BROKEN_LIST[@]} -gt 0 && "$FIX_DB" -eq 1 ]]; then
  for pid in "${BROKEN_LIST[@]}"; do
    m="mn|$pid"
    if [[ "${STATE[cn|$pid]}" == missing ]]; then
      log "$pid has no CN system metadata; use cn_force_accounting.sh for it"
      continue
    fi
    if [[ "${STATE[$m]}" != ok ]]; then
      log "$pid is not available on the MN; refusing to edit its CN links"
      continue
    fi
    sql="UPDATE systemmetadata SET obsoletes = $(sql_quote "${OBSOLETES[$m]}"), obsoleted_by = $(sql_quote "${OBSOLETED_BY[$m]}"), series_id = $(sql_quote "${SERIES[$m]}"), date_modified = now(), serial_version = (coalesce(nullif(serial_version, '')::bigint, 0) + 1)::varchar WHERE guid = $(sql_quote "$pid") RETURNING guid;"
    if [[ "$EXECUTE" -eq 1 ]]; then
      rows=$(db_exec "$sql" | wc -l | tr -d ' ')
      log "Updated systemmetadata for $pid ($rows row(s)); repeat on the sister CN"
    else
      log "DRY RUN (add --execute): $sql"
    fi
  done
  if [[ "$EXECUTE" -eq 1 ]]; then
    for pid in "${BROKEN_LIST[@]}"; do refetch_cn "$pid"; done
    collect_broken
  fi
fi

log "Final chain state:"
print_chain
if [[ ${#BROKEN_LIST[@]} -eq 0 ]]; then
  log "All CN chain links now match the MN"
  exit 0
fi
log "${#BROKEN_LIST[@]} link(s) still broken: ${BROKEN_LIST[*]}"
exit 1
