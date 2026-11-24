#!/usr/bin/env bash
##
# cn_object_sync.sh — privileged helper for moving metacat object-store files
# into place with correct tomcat:tomcat ownership, invoked via a narrowly
# scoped `sudo` rule by the unprivileged 'cnsync' account.
#
# This script exists so that the SSH account used for cross-CN object sync
# (cnsync) never needs read/write access to /var/metacat/documents, and never
# needs to log in as (or impersonate) the tomcat service account. All object
# store access and ownership changes happen here, as root, after this script
# validates its arguments.
#
# Install as root:root, mode 0700, at /usr/local/bin/cn_object_sync.sh, and
# permit only via sudoers, e.g. (/etc/sudoers.d/cn_object_sync):
#
#   Cmnd_Alias CN_OBJECT_SYNC = /usr/local/bin/cn_object_sync.sh exists *, \
#     /usr/local/bin/cn_object_sync.sh install *, \
#     /usr/local/bin/cn_object_sync.sh export *, \
#     /usr/local/bin/cn_object_sync.sh cleanup *
#   cnsync ALL=(root) NOPASSWD: CN_OBJECT_SYNC
#
# The 'cnsync' account itself should be created with no password, a
# restricted shell is not required (sudo is invoked explicitly), and its
# authorized_keys entry should include:
#   no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding
#
# Usage: cn_object_sync.sh {exists|install|export|cleanup} DOCID REV

set -euo pipefail

OBJECT_DIR="/var/metacat/documents"
STAGING_DIR="/var/lib/cn_object_sync/staging"
STAGING_OWNER="cnsync:cnsync"
OBJECT_OWNER="tomcat:tomcat"
OBJECT_MODE="640"

usage() {
  echo "Usage: $0 {exists|install|export|cleanup} DOCID REV" >&2
  exit 1
}

[[ $# -eq 3 ]] || usage
action="$1"
docid="$2"
rev="$3"

# docid/rev are attacker-controlled input from the calling account; only
# allow the character set metacat itself generates for these fields.
[[ "$docid" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "Invalid docid" >&2; exit 1; }
[[ "$rev" =~ ^[0-9]+$ ]] || { echo "Invalid rev" >&2; exit 1; }

object_path="${OBJECT_DIR}/${docid}.${rev}"
staged_path="${STAGING_DIR}/${docid}.${rev}"

mkdir -p "$STAGING_DIR"
chmod 700 "$STAGING_DIR"

case "$action" in
  exists)
    [[ -f "$object_path" ]]
    ;;
  install)
    # Move a file staged by cnsync (via scp) into the object store.
    [[ -f "$staged_path" ]] || { echo "Staged file not found: $staged_path" >&2; exit 1; }
    install -o root -g root -m "$OBJECT_MODE" "$staged_path" "$object_path"
    chown "$OBJECT_OWNER" "$object_path"
    rm -f "$staged_path"
    ;;
  export)
    # Copy an object-store file into the staging dir so cnsync can scp it out.
    [[ -f "$object_path" ]] || { echo "Object not found: $object_path" >&2; exit 1; }
    install -o "${STAGING_OWNER%%:*}" -g "${STAGING_OWNER##*:}" -m 600 "$object_path" "$staged_path"
    ;;
  cleanup)
    rm -f "$staged_path"
    ;;
  *)
    usage
    ;;
esac
