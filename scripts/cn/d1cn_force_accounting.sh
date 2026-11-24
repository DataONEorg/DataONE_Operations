#!/usr/bin/env bash
##
# Repair missing system metadata / purgatory Identifier rows by rebuilding
# systemmetadata entries directly from the member node, syncing the object
# payload to the sister CN when needed, and verifying the CN can see the object.
#
# Requires: curl, xmlstarlet, psql, ssh, scp
#
# Usage:
#   d1cn_force_accounting.sh [options] <NODE>
#
# Options:
#   --env ENV            Environment: dev, stage, sandbox, prod (default: prod)
#   --mn-base-url URL    Base URL of the MN (looked up from the CN if omitted)
#   --sister-host HOST   SSH host for the sister CN (or set CN_SISTER_HOST)
#   --sister-user USER   Unprivileged SSH user for the sister CN, e.g. cnsync
#                        (default: cnsync, or set SCP_USER)
#   --token-file FILE    Path to a file containing the member-node bearer token
#   --pid-file FILE      Use FILE instead of ~/force_sync/pid/NODE as the list
#                        of PIDs to repair (errors are still recorded next to
#                        this file, at FILE.err)
#   --verify-only        Only check the CN /meta endpoint for each PID in
#                        NODE's PID list; performs no database or object store
#                        changes. Run this after cn_force_accounting.sh has
#                        completed its normal (mutating) pass on BOTH sister
#                        CNs, since verification requires both CNs to already
#                        have the systemmetadata row and object in place.
#   --dry-run            Show what would be changed without mutating the DB or copying files
#   --debug              Verbose logging to stderr
#   -h, --help           Show this help text
#
# Object transfer:
#   Cross-CN object copies never SSH as root or as the tomcat service
#   account. --sister-user must be an unprivileged account (e.g. cnsync)
#   that stages files via scp and invokes remote/d1cnremote_object_sync.sh through a
#   narrowly scoped sudo rule on the sister CN; that wrapper is the only
#   thing that writes to /var/metacat/documents and sets tomcat:tomcat
#   ownership. See remote/d1cnremote_object_sync.sh for the required sudoers setup.
#
# Warning:
#   This script directly modifies the metacat postgres database and the object
#   store on the CN. It is intended for recovery from failed synchronization
#   states, and should be used with caution.

set -euo pipefail

declare -A ENV_BASE_URL=(
  [dev]="https://cn-dev.test.dataone.org/cn"
  [stage]="https://cn-stage.test.dataone.org/cn"
  [sandbox]="https://cn-sandbox.test.dataone.org/cn"
  [prod]="https://cn.dataone.org/cn"
)

ENV_NAME="prod"
MN_ID=""
MN_BASE_URL=""
TOKEN_FILE=""
PID_FILE_OVERRIDE=""
VERIFY_ONLY=0
SISTER_HOST="${CN_SISTER_HOST:-}"
SISTER_USER="${SCP_USER:-cnsync}"
REMOTE_WRAPPER="/usr/local/bin/d1cnremote_object_sync.sh"
REMOTE_STAGING_DIR="/var/lib/d1cnremote_object_sync/staging"
OBJECT_OWNER="tomcat:tomcat"
DEBUG=0
DRY_RUN=0
OUTDIR="$HOME/force_sync"
ERR_FILE=""
PIDS_FILE=""

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') INFO     $*" >&2
}

debug() {
  [[ "$DEBUG" -eq 1 ]] && echo "$(date '+%Y-%m-%d %H:%M:%S') DEBUG    $*" >&2
  return 0
}

xml_text() {
  local file="$1"
  local xpath="$2"
  xmlstarlet sel -t -m "$xpath" -v "." -n "$file" 2>/dev/null | head -n 1 || true
}

xml_attr() {
  local file="$1"
  local xpath="$2"
  local attr="$3"
  xmlstarlet sel -t -m "$xpath" -v "@${attr}" -n "$file" 2>/dev/null | head -n 1 || true
}

usage() {
  grep '^#' "$0" | sed -e 's/^#//' -e 's/^ //'
  exit 1
}

resolve_mn_base_url() {
  local token
  local node_list_file="$WORKDIR/nodelist.xml"
  local url

  if [[ -z "$TOKEN_FILE" || ! -r "$TOKEN_FILE" ]]; then
    echo "Error: TOKEN_FILE '$TOKEN_FILE' does not exist or is not readable" >&2
    exit 1
  fi

  token=$(tr -d '\r\n' < "$TOKEN_FILE")
  if [[ -z "$token" ]]; then
    echo "Error: TOKEN_FILE '$TOKEN_FILE' is empty" >&2
    exit 1
  fi

  log "Looking up base URL for $MN_ID from CN node list"
  curl -sS -f -H "Authorization: Bearer ${token}" "$CN_BASE_URL/v2/node" -o "$node_list_file"

  url=$(xml_text "$node_list_file" "//*[local-name()='node'][*[local-name()='identifier']='$MN_ID']/*[local-name()='baseURL']")
  if [[ -z "$url" ]]; then
    echo "Error: NodeId '$MN_ID' not found in CN node list and --mn-base-url not provided" >&2
    exit 1
  fi

  echo "$url"
}

sql_quote() {
  local value="${1:-}"
  if [[ -z "$value" ]]; then
    printf 'NULL'
    return
  fi
  value=${value//\\/\\\\}
  value=${value//"'"/"''"}
  printf "'%s'" "$value"
}

db_exec() {
  local sql="$1"
  sudo -u postgres psql -d metacat -v ON_ERROR_STOP=1 -At -c "$sql"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_NAME="$2"
      shift 2
      ;;
    --mn-base-url)
      MN_BASE_URL="$2"
      shift 2
      ;;
    --sister-host)
      SISTER_HOST="$2"
      shift 2
      ;;
    --sister-user)
      SISTER_USER="$2"
      shift 2
      ;;
    --token-file)
      TOKEN_FILE="$2"
      shift 2
      ;;
    --pid-file)
      PID_FILE_OVERRIDE="$2"
      shift 2
      ;;
    --verify-only)
      VERIFY_ONLY=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --debug)
      DEBUG=1
      shift
      ;;
    -h|--help)
      usage
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      ;;
    *)
      if [[ -z "$MN_ID" ]]; then
        MN_ID="$1"
      else
        echo "Unexpected argument: $1" >&2
        usage
      fi
      shift
      ;;
  esac
done

if [[ -z "$MN_ID" ]]; then
  echo "Error: mn_id is required" >&2
  usage
fi

if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  required_tools=(curl xmlstarlet)
else
  required_tools=(curl xmlstarlet psql scp ssh sudo)
fi
for tool in "${required_tools[@]}"; do
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

MN_NAME=${MN_ID##*:}
WORKDIR=$(mktemp -d)
SSH_CONTROL_PATH="$WORKDIR/ssh-ctrl.sock"
SSH_MUX_OPTS=(-o ControlMaster=auto -o ControlPath="$SSH_CONTROL_PATH" -o ControlPersist=60s)
cleanup() {
  # Close the shared multiplexed connection before removing WORKDIR, so no
  # ssh master process is left behind holding the (now-deleted) socket path.
  if [[ -S "$SSH_CONTROL_PATH" ]]; then
    ssh -o ControlPath="$SSH_CONTROL_PATH" -O exit "${SISTER_USER}@${SISTER_HOST}" 2>/dev/null || true
  fi
  rm -rf "$WORKDIR"
}
trap cleanup EXIT
mkdir -p "$OUTDIR/token" "$OUTDIR/pid"

if [[ -z "$TOKEN_FILE" ]]; then
  TOKEN_FILE="$OUTDIR/token/${MN_NAME}"
fi

if [[ ! -r "$TOKEN_FILE" ]]; then
  echo "Error: TOKEN_FILE '$TOKEN_FILE' does not exist or is not readable" >&2
  exit 1
fi

if [[ "$VERIFY_ONLY" -ne 1 ]]; then
  if [[ -z "$MN_BASE_URL" ]]; then
    MN_BASE_URL=$(resolve_mn_base_url)
  fi
  log "MN base URL = $MN_BASE_URL"
fi

PIDS_FILE="${PID_FILE_OVERRIDE:-$OUTDIR/pid/${MN_NAME}.force}"
ERR_FILE="${PIDS_FILE}.err"
: > "$ERR_FILE"

if [[ ! -s "$PIDS_FILE" ]]; then
  log "No unsynchronized PID list found at $PIDS_FILE for $MN_ID. Run cn_synchronize.sh first."
  exit 0
fi

if [[ "$VERIFY_ONLY" -ne 1 ]]; then
  if [[ -z "$SISTER_HOST" ]]; then
    log "No sister CN host configured. Set --sister-host or CN_SISTER_HOST to enable object sync."
    exit 1
  fi

  if [[ "$SISTER_USER" == "root" || "$SISTER_USER" == "tomcat" ]]; then
    echo "Error: --sister-user must be an unprivileged sync account (e.g. cnsync), not root or tomcat." >&2
    echo "See remote/d1cnremote_object_sync.sh for the required sudo/staging setup." >&2
    exit 1
  fi
fi

remote_ssh() {
  # -n keeps ssh from reading the PID list that's redirected onto the main
  # loop's stdin; without it, ssh drains the rest of PIDS_FILE and the loop
  # silently stops after the first remote call. ControlMaster/ControlPersist
  # reuse one connection for the whole run instead of opening a fresh ssh
  # session (and knownhostsproxy handshake) per call.
  ssh -n -o BatchMode=yes -o ConnectTimeout=10 "${SSH_MUX_OPTS[@]}" "${SISTER_USER}@${SISTER_HOST}" "$@"
}

check_remote_object() {
  local docid="$1"
  local rev="$2"
  remote_ssh "sudo ${REMOTE_WRAPPER} exists '${docid}' '${rev}'"
}

transfer_object() {
  local docid="$1"
  local rev="$2"
  local local_path="/var/metacat/documents/${docid}.${rev}"

  if ! mkdir -p "$(dirname "$local_path")"; then
    log "Failed to create local object directory for ${docid}.${rev}"
    return 1
  fi

  local remote_has=0
  if check_remote_object "$docid" "$rev" >/dev/null 2>&1; then
    remote_has=1
  fi

  if [[ -f "$local_path" ]]; then
    if [[ "$remote_has" -eq 1 ]]; then
      log "Object exists on both local and sister CN for ${docid}.${rev}; skipping transfer"
      return 0
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
      log "DRY RUN: stage '$local_path' to sister CN and install via sudo ${REMOTE_WRAPPER}"
      return 0
    fi
    # Stage the file as the unprivileged sync user, then let the remote
    # sudo wrapper move it into the object store and set tomcat:tomcat.
    # REMOTE_STAGING_DIR must already exist, owned by SISTER_USER, from setup.
    if ! scp -p "${SSH_MUX_OPTS[@]}" "$local_path" "${SISTER_USER}@${SISTER_HOST}:${REMOTE_STAGING_DIR}/${docid}.${rev}"; then
      log "Failed to stage ${docid}.${rev} on sister CN via scp"
      return 1
    fi
    if ! remote_ssh "sudo ${REMOTE_WRAPPER} install '${docid}' '${rev}'"; then
      log "Failed to install staged object ${docid}.${rev} on sister CN"
      return 1
    fi
    log "Copied object ${docid}.${rev} to sister CN"
    return 0
  fi

  if [[ "$remote_has" -eq 1 ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      log "DRY RUN: export ${docid}.${rev} on sister CN via sudo ${REMOTE_WRAPPER} and pull it"
      return 0
    fi
    # Ask the remote sudo wrapper to stage a readable copy for cnsync, pull
    # it, then set local ownership to match the object store convention.
    if ! remote_ssh "sudo ${REMOTE_WRAPPER} export '${docid}' '${rev}'"; then
      log "Failed to export ${docid}.${rev} on sister CN"
      return 1
    fi
    if ! scp -p "${SSH_MUX_OPTS[@]}" "${SISTER_USER}@${SISTER_HOST}:${REMOTE_STAGING_DIR}/${docid}.${rev}" "$local_path"; then
      log "Failed to pull ${docid}.${rev} from sister CN"
      remote_ssh "sudo ${REMOTE_WRAPPER} cleanup '${docid}' '${rev}'" || true
      return 1
    fi
    remote_ssh "sudo ${REMOTE_WRAPPER} cleanup '${docid}' '${rev}'" || true
    chown "$OBJECT_OWNER" "$local_path" 2>/dev/null || log "Warning: could not chown $local_path to $OBJECT_OWNER"
    log "Pulled object ${docid}.${rev} from sister CN"
    return 0
  fi

  log "No object available locally or on sister CN for ${docid}.${rev}"
  return 1
}

verify_cn_knows_pid() {
  local guid="$1"
  local xml_file="$WORKDIR/verify_${guid//[^A-Za-z0-9_.-]/_}.xml"
  local response

  response=$(curl -sS -f -H "Authorization: Bearer $(tr -d '\r\n' < "$TOKEN_FILE")" "${CN_BASE_URL}/v2/meta/${guid}" -o "$xml_file" 2>/dev/null || true)

  if [[ -z "$response" && ! -s "$xml_file" ]]; then
    echo "$guid" >> "$ERR_FILE"
    log "Verification failed for $guid: error retrieving /v2/meta/$guid from CN"
    return 1
  fi

  local id_value
  id_value=$(xml_text "$xml_file" "//*[local-name()='identifier']" || true)
  if [[ -z "$id_value" ]]; then
    echo "$guid" >> "$ERR_FILE"
    log "Verification failed for $guid: no identifier found in /v2/meta/$guid response"
    return 1
  fi

  if [[ "$id_value" != "$guid" ]]; then
    echo "$guid" >> "$ERR_FILE"
    log "Verification failed for $guid: CN reported identifier '$id_value' instead of '$guid'"
    return 1
  fi

  return 0
}

insert_systemmetadata_record() {
  local guid="$1"
  local docid="$2"
  local rev="$3"
  local xml_file="$4"

  local serial_version date_uploaded rights_holder checksum checksum_algorithm origin_member_node authoritive_member_node date_modified submitter object_format size archived replication_allowed number_replicas obsoletes obsoleted_by series_id media_type file_name

  serial_version=$(xml_text "$xml_file" "//*[local-name()='serialVersion']")
  date_uploaded=$(xml_text "$xml_file" "//*[local-name()='dateUploaded']")
  rights_holder=$(xml_text "$xml_file" "//*[local-name()='rightsHolder']")
  checksum=$(xml_text "$xml_file" "//*[local-name()='checksum']")
  checksum_algorithm=$(xml_attr "$xml_file" "//*[local-name()='checksum']" "algorithm")
  if [[ -z "$checksum_algorithm" ]]; then
    checksum_algorithm=$(xml_text "$xml_file" "//*[local-name()='checksumAlgorithm']")
  fi
  origin_member_node=$(xml_text "$xml_file" "//*[local-name()='originMemberNode']")
  authoritative_member_node=$(xml_text "$xml_file" "//*[local-name()='authoritativeMemberNode']")
  date_modified=$(xml_text "$xml_file" "//*[local-name()='dateSysMetadataModified']")
  submitter=$(xml_text "$xml_file" "//*[local-name()='submitter']")
  object_format=$(xml_text "$xml_file" "//*[local-name()='formatId']")
  if [[ -z "$object_format" ]]; then
    object_format=$(xml_text "$xml_file" "//*[local-name()='objectFormat']")
  fi
  size=$(xml_text "$xml_file" "//*[local-name()='size']")
  archived=$(xml_text "$xml_file" "//*[local-name()='archived']")
  replication_allowed=$(xml_attr "$xml_file" "//*[local-name()='replicationPolicy']" "replicationAllowed")
  number_replicas=$(xml_attr "$xml_file" "//*[local-name()='replicationPolicy']" "numberReplicas")
  obsoletes=$(xml_text "$xml_file" "//*[local-name()='obsoletes']")
  obsoleted_by=$(xml_text "$xml_file" "//*[local-name()='obsoletedBy']")
  series_id=$(xml_text "$xml_file" "//*[local-name()='seriesId']")
  media_type=$(xml_attr "$xml_file" "//*[local-name()='mediaType']" "name")
  file_name=$(xml_text "$xml_file" "//*[local-name()='fileName']")

  local sql
  sql=$(cat <<SQL
INSERT INTO systemmetadata (
  guid,
  serial_version,
  date_uploaded,
  rights_holder,
  checksum,
  checksum_algorithm,
  origin_member_node,
  authoritive_member_node,
  date_modified,
  submitter,
  object_format,
  size,
  archived,
  replication_allowed,
  number_replicas,
  obsoletes,
  obsoleted_by,
  series_id,
  media_type,
  file_name
) VALUES (
  $(sql_quote "$guid"),
  $(sql_quote "$serial_version"),
  $(sql_quote "$date_uploaded"),
  $(sql_quote "$rights_holder"),
  $(sql_quote "$checksum"),
  $(sql_quote "$checksum_algorithm"),
  $(sql_quote "$origin_member_node"),
  $(sql_quote "$authoritative_member_node"),
  $(sql_quote "$date_modified"),
  $(sql_quote "$submitter"),
  $(sql_quote "$object_format"),
  $(sql_quote "$size"),
  $(sql_quote "$archived"),
  $(sql_quote "$replication_allowed"),
  $(sql_quote "$number_replicas"),
  $(sql_quote "$obsoletes"),
  $(sql_quote "$obsoleted_by"),
  $(sql_quote "$series_id"),
  $(sql_quote "$media_type"),
  $(sql_quote "$file_name")
);
SQL
)

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY RUN: $sql"
    return 0
  fi

  if ! db_exec "$sql"; then # >/dev/null 2>&1; then
    echo "$guid" >> "$ERR_FILE"
    log "Failed to insert systemmetadata for $guid"
    return 1
  fi

  log "Inserted systemmetadata for $guid"
  return 0
}

insert_xml_access_record() {
  local guid="$1"

  # Grants default public read access, matching the row metacat itself
  # creates for a public object: permission 4 (read), perm_type allow,
  # perm_order allowFirst, no accessfileid/subtree/node scoping.
  local sql
  sql=$(cat <<SQL
INSERT INTO xml_access (
  guid,
  accessfileid,
  principal_name,
  permission,
  perm_type,
  perm_order
) VALUES (
  $(sql_quote "$guid"),
  NULL,
  $(sql_quote "public"),
  4,
  $(sql_quote "allow"),
  $(sql_quote "allowFirst")
);
SQL
)

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY RUN: $sql"
    return 0
  fi

  if ! db_exec "$sql"; then
    echo "$guid" >> "$ERR_FILE"
    log "Failed to insert xml_access for $guid"
    return 1
  fi

  log "Inserted xml_access for $guid"
  return 0
}

if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  # Standalone verification pass: no DB or object store changes, just check
  # that the CN now reports each PID via /meta. Intended to be run after the
  # normal mutating pass has completed on both sister CNs.
  count=0
  while IFS= read -r guid; do
    [[ -z "$guid" ]] && continue
    count=$((count + 1))
    if verify_cn_knows_pid "$guid"; then
      log "Verified $count: $guid is known to the CN"
    fi
  done < "$PIDS_FILE"

  if [[ "$count" -eq 0 ]]; then
    log "No records were processed."
  fi

  if [[ -s "$ERR_FILE" ]]; then
    log "The following identifiers failed verification:"
    cat "$ERR_FILE" >&2
  else
    log "No errors were encountered."
  fi

  exit 0
fi

count=0
while IFS= read -r guid <&3; do
  [[ -z "$guid" ]] && continue
  count=$((count + 1))

  docid_rev=$(db_exec "SELECT docid || '|' || rev FROM identifier WHERE guid = $(sql_quote "$guid") LIMIT 1;" 2>/dev/null || true)
  if [[ -z "$docid_rev" ]]; then
    echo "$guid" >> "$ERR_FILE"
    log "No identifier row found for PID $guid in the metacat database; skipped"
    continue
  fi

  docid=${docid_rev%%|*}
  rev=${docid_rev#*|}
  if [[ -z "$docid" || -z "$rev" || "$docid_rev" == "$docid" || "$docid_rev" == "$rev" ]]; then
    echo "$guid" >> "$ERR_FILE"
    log "Identifier row for PID $guid is incomplete (docid=$docid rev=$rev); skipped"
    continue
  fi

  has_sysmeta=0
  if db_exec "SELECT 1 FROM systemmetadata WHERE guid = $(sql_quote "$guid") LIMIT 1;" | grep -q '^1$'; then
    has_sysmeta=1
  fi

  log "Processing $count: $guid (docid=$docid, rev=$rev)"

  if [[ "$has_sysmeta" -eq 1 ]]; then
    log "PID $guid already has a systemmetadata row; skipping insert, running access/copy checks"
  else
    meta_file="$WORKDIR/meta_${guid//[^A-Za-z0-9_.-]/_}.xml"
    token=$(tr -d '\r\n' < "$TOKEN_FILE")
    if ! curl -sS -f -H "Authorization: Bearer ${token}" "${MN_BASE_URL}/v2/meta/${guid}" -o "$meta_file"; then
      echo "$guid" >> "$ERR_FILE"
      log "Could not fetch metadata for $guid from $MN_BASE_URL; skipped"
      continue
    fi

    if ! insert_systemmetadata_record "$guid" "$docid" "$rev" "$meta_file"; then
      continue
    fi
  fi

  if ! db_exec "SELECT 1 FROM xml_access WHERE guid = $(sql_quote "$guid") AND principal_name = 'public' LIMIT 1;" | grep -q '^1$'; then
    if ! insert_xml_access_record "$guid"; then
      continue
    fi
  else
    log "PID $guid already has a public xml_access row; skipping"
  fi

  if ! transfer_object "$docid" "$rev"; then
    echo "$guid" >> "$ERR_FILE"
    log "Object transfer failed for $guid (docid=$docid, rev=$rev); skipped"
    continue
  fi

done 3< "$PIDS_FILE"

if [[ "$count" -eq 0 ]]; then
  log "No records were processed."
fi

if [[ -s "$ERR_FILE" ]]; then
  log "The following identifiers were not repaired successfully:"
  cat "$ERR_FILE" >&2
else
  log "No errors were encountered."
fi
