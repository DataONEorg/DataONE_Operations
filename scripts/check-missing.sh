#!/bin/bash
#
# check-missing.sh - Compare a Member Node's object list with the CN's and
# report PIDs that the MN holds but the CN has not synchronized properly.
#
# Usage: check-missing.sh [--check-sysmeta true|false] NODE_ID
#        (NODE_ID e.g. CA_OPC or urn:node:CA_OPC)
#
#   By default the script only compares the two object lists and prints the
#   summary counts.
#
#   --check-sysmeta true  also check each candidate PID against the CN's
#                         system metadata and classify it (404 missing,
#                         authoritative node mismatch, 401 not readable).
#                         Slow for large nodes: one CN request per candidate.
#                         Default: false. A bare --check-sysmeta or
#                         --check-sysmeta=true also works.
#
# Requires: curl (7.55+), xmlstarlet (xml)
#
# Optional environment variables:
#   CN_TOKEN  JWT for the CN (e.g. CN admin) so private objects are visible
#   MN_TOKEN  JWT for the MN (e.g. MN admin)
#   JOBS      number of parallel CN system metadata checks (default 8)
#   PAGE      objects requested per listObjects page (default 7000; servers
#             may return fewer, and the script adapts to what they return)
#   PAGE_JOBS parallel page downloads per list (default 4); the MN and CN
#             lists download at the same time, so 2x this many in total
#
# Progress messages go to stderr; the report goes to stdout.

set -euo pipefail

CN="https://cn.dataone.org/cn/v2"
PAGE=${PAGE:-7000}           # objects requested per listObjects call
PAGE_JOBS=${PAGE_JOBS:-4}    # parallel page downloads per list
JOBS=${JOBS:-8}              # parallel getSystemMetadata calls

usage() {
    echo "Usage: $0 [--check-sysmeta true|false] NODE_ID   (e.g. CA_OPC)" >&2
    exit 1
}

# Accept true/false (any case); anything else is an error
bool() {
    case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
        true)  echo true ;;
        false) echo false ;;
        *) echo "Invalid value for --check-sysmeta: '$1' (use true or false)" >&2; exit 1 ;;
    esac
}

CHECK_SYSMETA=false
NODE_ARG=""
while [ $# -gt 0 ]; do
    case "$1" in
        --check-sysmeta=*) CHECK_SYSMETA=$(bool "${1#*=}") ;;
        --check-sysmeta)
            # Value is optional: consume the next arg only if it is a boolean
            case "$(printf '%s' "${2:-}" | tr '[:upper:]' '[:lower:]')" in
                true|false) CHECK_SYSMETA=$(bool "$2"); shift ;;
                *) CHECK_SYSMETA=true ;;
            esac ;;
        -h|--help) usage ;;
        -*) echo "Unknown option: $1" >&2; usage ;;
        *)  [ -z "$NODE_ARG" ] || usage; NODE_ARG=$1 ;;
    esac
    shift
done
[ -n "$NODE_ARG" ] || usage
NODE_ID="urn:node:${NODE_ARG#urn:node:}"

TMP=$(mktemp -d)   # mode 700, so token header files stay private
trap 'rm -rf "$TMP"' EXIT

# Tokens go in header files (curl -H @file) so they never appear in `ps`.
: > "$TMP/cn.hdr"; : > "$TMP/mn.hdr"
if [ -n "${CN_TOKEN:-}" ]; then echo "Authorization: Bearer $CN_TOKEN" > "$TMP/cn.hdr"; fi
if [ -n "${MN_TOKEN:-}" ]; then echo "Authorization: Bearer $MN_TOKEN" > "$TMP/mn.hdr"; fi

# Look up the MN base URL in the CN node registry
MN_BASE=$(curl -sf "$CN/node" |
    xml sel -t -m "//node[identifier='$NODE_ID']" -v "baseURL" -n | head -1 || true)
if [ -z "$MN_BASE" ]; then
    echo "Node $NODE_ID not found in $CN/node" >&2
    exit 1
fi
MN="$MN_BASE/v2"

# Print the total object count for a listObjects URL ($1) using header file $2
total() {
    curl -sf -H @"$2" "$1&count=0" |
        xml sel -t -v "/*[local-name()='objectList']/@total"
}

# Fetch one listObjects page and save its PIDs to DIR/START.pids
#   fetch_page LABEL DIR URL HDR COUNT NPAGES START
# Retries 3 times; exits 255 on failure so xargs stops the whole download.
fetch_page() {
    local label=$1 dir=$2 url=$3 hdr=$4 count=$5 npages=$6 start=$7 try done
    for try in 1 2 3; do
        if curl -sf -H @"$hdr" "$url&start=$start&count=$count" > "$dir/$start.xml" &&
           xml sel -t -v "/*/@count" "$dir/$start.xml" > /dev/null 2>&1; then
            xml sel -t -m "//objectInfo" -v "identifier" -n "$dir/$start.xml" \
                > "$dir/$start.part" || true
            mv "$dir/$start.part" "$dir/$start.pids"
            rm -f "$dir/$start.xml"
            done=$(find "$dir" -name '*.pids' | wc -l | tr -d ' ')
            echo "$label list: page $done/$npages" >&2
            return 0
        fi
        sleep $((try * 2))
    done
    echo "$label list: failed to fetch page at start=$start after 3 tries" >&2
    exit 255
}
export -f fetch_page

# Download every PID from a listObjects URL into OUT, pages in parallel.
#   list_pids LABEL URL HDR OUT     (also writes the reported total to OUT.total)
list_pids() {
    local label=$1 url=$2 hdr=$3 out=$4 dir n stride npages
    dir=$(mktemp -d "$TMP/$label.XXXX")

    # Fetch the first page to learn the total and the server's real page
    # size (servers cap count, e.g. at 7000), then fetch the rest in parallel.
    curl -sf -H @"$hdr" "$url&start=0&count=$PAGE" > "$dir/first.xml"
    n=$(xml sel -t -v "/*/@total" "$dir/first.xml")
    stride=$(xml sel -t -v "/*/@count" "$dir/first.xml")
    echo "$n" > "$out.total"
    xml sel -t -m "//objectInfo" -v "identifier" -n "$dir/first.xml" \
        > "$dir/0.pids" || true
    rm -f "$dir/first.xml"

    if [ "$stride" -gt 0 ] && [ "$n" -gt "$stride" ]; then
        npages=$(( (n + stride - 1) / stride ))
        echo "$label list: $n objects, $npages pages of $stride" >&2
        echo "$label list: page 1/$npages" >&2
        # (not seq: macOS seq prints 1.001e+06 above a million)
        awk -v s="$stride" -v n="$n" 'BEGIN { for (i = s; i < n; i += s) print i }' |
            xargs -n 1 -P "$PAGE_JOBS" bash -c \
                'fetch_page "$@"' _ "$label" "$dir" "$url" "$hdr" "$stride" "$npages"
    else
        echo "$label list: $n objects, 1 page" >&2
    fi
    cat "$dir"/*.pids | sort -u > "$out"
    echo "$label list: done ($(wc -l < "$out" | tr -d ' ') unique PIDs)" >&2
}

# URL-encode a string for use in a path segment
urlencode() {
    local s=$1 out="" c i
    for ((i = 0; i < ${#s}; i++)); do
        c=${s:i:1}
        case "$c" in
            [a-zA-Z0-9.~_-]) out+="$c" ;;
            *) out+=$(printf '%%%02X' "'$c") ;;
        esac
    done
    printf '%s' "$out"
}

# Fetch CN system metadata for one PID and print:
#   HTTP_CODE <tab> CN_AUTHORITATIVE_NODE <tab> PID
check_one() {
    local pid=$1 resp code auth try
    for try in 1 2 3 4 5; do
        auth=""
        resp=$(curl -s -H @"$CN_HDR" -w '\n%{http_code}' "$CN/meta/$(urlencode "$pid")")
        code=${resp##*$'\n'}
        case "$code" in
            401|404) break ;;
            200) auth=$(printf '%s' "${resp%$'\n'*}" |
                     xml sel -t -v "/*/authoritativeMemberNode" 2>/dev/null || true)
                 [ -n "$auth" ] && break ;;
        esac
        # Transient error (e.g. 503 when the CN is busy) or truncated
        # response: back off 2, 4, 8, 16 s before retrying
        if [ "$try" -lt 5 ]; then sleep $((1 << try)); fi
    done
    if [ "$code" = "200" ] && [ -z "$auth" ]; then auth="(unknown)"; fi
    # Append one complete line in a single write; O_APPEND (>>) keeps
    # parallel workers from overwriting or splitting each other's lines.
    local line
    printf -v line '%s\t%s\t%s\n' "$code" "$auth" "$pid"
    printf '%s' "$line" >> "$CHECK_RESULTS"

    # Progress: one byte per finished check; report every 500 and at the end
    local n
    printf . >> "$CHECK_DONE"
    n=$(wc -c < "$CHECK_DONE" | tr -d ' ')
    if [ $((n % 500)) -eq 0 ] || [ "$n" -eq "$CHECK_TOTAL" ]; then
        echo "sysmeta checks: $n/$CHECK_TOTAL" >&2
    fi
}
# Look up one batch of PIDs (a file, one per line) in the CN Solr index and
# write to BATCH.out, for each PID found under a node other than NODE_ID:
#   200 <tab> CN_DATASOURCE_NODE <tab> PID
# PIDs not found (e.g. not indexed, or private without a token) are left out
# and fall through to the individual system metadata check. A batch that
# fails after 3 tries also prints nothing, so its PIDs fall through too.
solr_batch() {
    local batch=$1 q try n nb
    # id:("pid1" OR "pid2" ...), escaping backslashes and double quotes
    q=$(awk 'BEGIN { ORS = ""; print "id:(" }
             { gsub(/\\/, "\\\\"); gsub(/"/, "\\\"");
               printf "%s\"%s\"", (NR > 1 ? " OR " : ""), $0 }
             END { print ")" }' "$batch")
    n=$(wc -l < "$batch" | tr -d ' ')
    for try in 1 2 3; do
        # The CN Solr endpoint accepts POST only as multipart/form-data
        if curl -sf -H @"$CN_HDR" -X POST "$CN/query/solr/" \
                --form-string "q=$q" --form-string "fl=id,datasource" \
                --form-string "rows=$n" --form-string "wt=xml" > "$batch.xml" &&
           xml sel -t -v "//result/@numFound" "$batch.xml" > /dev/null 2>&1; then
            # Each batch writes its own file: parallel batches writing to one
            # shared stdout interleave their output and corrupt lines.
            xml sel -t -m "//result/doc" -v "str[@name='datasource']" -o $'\t' \
                -v "str[@name='id']" -n "$batch.xml" |
                awk -F'\t' -v me="$NODE_ID" '$1 != "" && $1 != me { print "200\t" $0 }' \
                > "$batch.out"
            break
        fi
        sleep $((try * 2))
    done
    printf . >> "$SOLR_DONE"
    nb=$(wc -c < "$SOLR_DONE" | tr -d ' ')
    echo "CN Solr batches: $nb/$SOLR_TOTAL" >&2
}

export -f check_one urlencode solr_batch
export CN NODE_ID
export CN_HDR="$TMP/cn.hdr"
export CHECK_DONE="$TMP/checks.done"
export CHECK_RESULTS="$TMP/results"
export SOLR_DONE="$TMP/solr.done"
SOLR_BATCH=${SOLR_BATCH:-500}   # PIDs per Solr query (Solr caps OR clauses at 1024)

MN_URL="$MN/object?replicaStatus=false"
CN_URL="$CN/object?nodeId=$(printf '%s' "$NODE_ID" | sed 's/:/%3A/g')"

# Kill a process and all of its descendants (e.g. a list job and its xargs)
killtree() {
    local child
    for child in $(pgrep -P "$1" 2>/dev/null); do killtree "$child"; done
    kill "$1" 2>/dev/null || true
}

# Download the MN and CN lists at the same time
list_pids MN "$MN_URL" "$TMP/mn.hdr" "$TMP/mn" & mn_job=$!
list_pids CN "$CN_URL" "$TMP/cn.hdr" "$TMP/cn" & cn_job=$!
if ! wait "$mn_job"; then
    echo "MN list download failed" >&2
    killtree "$cn_job"; wait "$cn_job" 2>/dev/null || true
    exit 1
fi
wait "$cn_job" || { echo "CN list download failed" >&2; exit 1; }
mn_total=$(cat "$TMP/mn.total")
cn_total=$(cat "$TMP/cn.total")

# Even with replicaStatus=false, the MN list can include objects whose MN
# system metadata names this node as authoritative while the CN lists them
# under another node. Classify each candidate in two passes:
#   1. Batch lookups in the CN Solr index. A PID found there is on the CN
#      under the indexed datasource node (mismatch). Fast, but the index
#      does not hold everything (e.g. many resource maps are not indexed).
#   2. Individual CN getSystemMetadata calls for the PIDs Solr didn't find:
#        404 = not on the CN (missing)
#        401 = on the CN but not readable with the credentials given
#        200 = on the CN, but under a different authoritative node (mismatch)
count() { wc -l < "$1" | tr -d ' '; }

comm -23 "$TMP/mn" "$TMP/cn" > "$TMP/candidates"
: > "$TMP/results"; : > "$TMP/solr_results"; : > "$TMP/remaining"
if [ "$CHECK_SYSMETA" = true ] && [ -s "$TMP/candidates" ]; then
    mkdir "$TMP/solr"
    split -l "$SOLR_BATCH" "$TMP/candidates" "$TMP/solr/batch."
    : > "$SOLR_DONE"
    export SOLR_TOTAL=$(ls "$TMP/solr" | wc -l | tr -d ' ')
    echo "CN Solr: $(count "$TMP/candidates") candidates in $SOLR_TOTAL batches" \
         "of up to $SOLR_BATCH, $JOBS at a time" >&2
    ls "$TMP/solr"/batch.* | tr '\n' '\0' |
        xargs -0 -n 1 -P "$JOBS" bash -c 'solr_batch "$1"' _
    cat "$TMP/solr"/*.out 2>/dev/null > "$TMP/solr_results" || true

    # Anything Solr didn't resolve gets an individual sysmeta check
    cut -f3 "$TMP/solr_results" | sort -u > "$TMP/solr_found"
    comm -23 "$TMP/candidates" "$TMP/solr_found" > "$TMP/remaining"
    if [ -s "$TMP/remaining" ]; then
        : > "$CHECK_DONE"
        export CHECK_TOTAL=$(count "$TMP/remaining")
        echo "sysmeta checks: $CHECK_TOTAL not resolved by Solr, $JOBS at a time" >&2
        tr '\n' '\0' < "$TMP/remaining" |
            xargs -0 -n 1 -P "$JOBS" bash -c 'check_one "$1"' _
    fi
    cat "$TMP/solr_results" >> "$TMP/results"
fi

awk -F'\t' '$1 == 404 { print $3 }' "$TMP/results" | sort > "$TMP/404"
awk -F'\t' '$1 == 401 { print $3 }' "$TMP/results" | sort > "$TMP/401"
awk -F'\t' '$1 == 200 { print $2 "\t" $3 }' "$TMP/results" | sort > "$TMP/mismatch"
awk -F'\t' '$1 != 200 && $1 != 401 && $1 != 404 { print $1 "\t" $3 }' \
    "$TMP/results" | sort > "$TMP/other"

yn() { if [ -s "$1" ]; then echo yes; else echo no; fi; }

# ---- Summary -------------------------------------------------------------
echo "# Sync check: $NODE_ID"
echo
echo "MN: $MN_BASE (tokens: CN=$(yn "$TMP/cn.hdr"), MN=$(yn "$TMP/mn.hdr"))"
echo
echo "- MN Count: $mn_total"
echo "- CN Count: $cn_total"
echo "- Candidates not in CN list for $NODE_ID: $(count "$TMP/candidates")"
if [ "$CHECK_SYSMETA" = false ]; then
    echo "    - Not classified (run with --check-sysmeta true to check" \
         "each candidate against the CN)"
    exit 0
fi
echo "    - Classified via CN Solr: $(count "$TMP/solr_results");" \
     "via individual sysmeta: $(count "$TMP/remaining")"
echo "    - Missing from CN (404): $(count "$TMP/404")"
echo "    - Authoritative node mismatch: $(count "$TMP/mismatch")"
if [ -s "$TMP/mismatch" ]; then
    echo "      - Counts by CN authoritative node:"
    cut -f1 "$TMP/mismatch" | sort | uniq -c | sort -rn |
        awk '{ print "          - " $1 " " $2 }'
fi
if [ -s "$TMP/401" ]; then
    echo "    - On CN but not readable (401): $(count "$TMP/401") (set CN_TOKEN to see these)"
fi
if [ -s "$TMP/other" ]; then
    echo "    - Unexpected responses: $(count "$TMP/other")"
fi

# ---- Detail sections -----------------------------------------------------
# Print a section heading and its PID list (only if the list is non-empty)
section() {
    local title=$1 file=$2 note=${3:-}
    [ -s "$file" ] || return 0
    echo
    echo "## $title ($(count "$file"))"
    echo
    if [ -n "$note" ]; then echo "$note"; echo; fi
    sed 's/^/- /' "$file"
}

section "Missing from CN (404)" "$TMP/404" \
    "PIDs on $NODE_ID that the CN has no system metadata for."

# One mismatch section per CN authoritative node
cut -f1 "$TMP/mismatch" | sort -u | while IFS= read -r node; do
    awk -F'\t' -v n="$node" '$1 == n { print $2 }' "$TMP/mismatch" > "$TMP/mm_node"
    section "Authoritative node mismatch: CN says $node" "$TMP/mm_node" \
        "MN system metadata names $NODE_ID as authoritative; the CN names $node."
done

section "On CN but not readable (401)" "$TMP/401" \
    "The CN has these objects but they are not readable with the credentials given."

if [ -s "$TMP/other" ]; then
    sed 's/\t/ /' "$TMP/other" > "$TMP/other_fmt"
    section "Unexpected responses (HTTP code, PID)" "$TMP/other_fmt"
fi
