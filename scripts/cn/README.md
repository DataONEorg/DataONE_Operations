## DataONE_Operations/cn: CN bookkeeping scripts
A set of scripts to ensure the DataONE coordinating nodes have synchronized metacat objects and system metadata for each.

- **Authors**: Nesbitt, Ian ([0000-0001-5828-6070](http://orcid.org/0000-0001-5828-6070)); Tao, Jing ([0000-0002-1209-5268](http://orcid.org/00000-0002-1209-5268))
- **License**: [Apache 2](http://opensource.org/licenses/Apache-2.0)
- [Package source code on GitHub](https://github.com/DataONEorg/DataONE_Operations)
- [**Submit Bugs and feature requests**](https://github.com/DataONEorg/DataONE_Operations/issues)
- Contact us: support@dataone.org
- [DataONE discussions](https://github.com/DataONEorg/dataone/discussions)

*A set of scripts to ensure the DataONE coordinating nodes have synchronized metacat objects and system metadata for each.* Connection issues have resulted in many failed and partial syncs of objects and system metadata documents between the DataONE member nodes and CNs. Sometimes, objects can be remedially synced simply with a forced synchronization using a member node long-lived token and the `/synchronize` endpoint in the DataONE CN API. However, objects that have been partially synced but not fully removed from postgres due to Hazelcast connection issues exist in a purgatory state where there may be a metacat object present on one of the CNs, and an entry in the `identifier` postgres table of both CNs linking that object to a PID, but no `systemmetadata` entry to match.

This software is designed to remedy the issue using one or both of two steps with increasing forcefulness. In the case where an object sync simply fails, the first and least risky remedy is to try to `/synchronize` the object again using `synchronize.sh`. This script produces a list of PIDs that exist on the MN but not the CN, and optionally `--force-sync`s them to the CN. However, if objects first fail to sync with `CONCURRENT_MAP_CONTAINS_KEY` and then an `IdentifierNotUnique` error, they are likely in the sort of purgatory state described above and must be synced more forcefully by circumventing the API and modifying the postgres databases and metacat object stores on each CN directly.

For these objects, administrators must modify the `metacat` postgres databases directly. `systemmetadata` values must be extracted from the MN `/meta` endpoint for the object in question, parsed, and inserted directly into the table for each `identifier` that does not have a corresponding `systemmetadata` entry. The CN metacat object must also be securely copied (`scp`) to the other CN metacat object store if they failed to sync using the API. Once a `systemmetadata`, `identifier` and object store entry exist on both CNs, the script can call the `/meta/PID` endpoint to force the CN to become aware of the change and verify that the object is now properly accounted for.

DataONE in general, and `DataONE_Operations` in particular, are open source, community projects.  We [welcome contributions](./CONTRIBUTING.md) in many forms, including code, graphics, documentation, bug reports, testing, etc.  Use the [DataONE discussions](https://github.com/DataONEorg/dataone/discussions) to discuss these contributions with us.


## Documentation

Documentation is a work in progress, and can be found ...

## Installation

This is a linux-tested bash script. It has not been tested on Darwin (Mac OS) systems.

To install locally, clone the repo, and ensure `xmlstarlet` is installed on the system (`xmlstarlet --version`). Since it's run on the CN, it also assumes postgres and metacat are installed and that the standard suite of Ubuntu tools are available—specifically curl, ssh, and scp. The user running the script should have sudo privileges.

## Usage Example

For more information, call a script with the `-h` help flag.

## Security disclaimer

Always ensure any sensitive information is encrypted, or at least isolated to only the user. `chmod 600 ~/force_sync/token/*` is preferred for token protection, but do not leave token files on disk after use. Making use of decryption via the security repo is strongly encouraged.

### d1cn_synchronize.sh

Requires a member node token file at `~/force_sync/token/NODE`, where NODE is the shortened nodeId of the MN (i.e. `UCSB1` for a nodeId of `urn:node:UCSB1`).
This script will output a plain text list of un-synchronized PIDs to `~/force_sync/pid/NODE`.

To force a synchronization of the un-synchronized PIDs list using the CN `/synchronize` API endpoint, set the `--force-sync` flag option.

To use the current `~/force_sync/pid/NODE` file without querying the MN or CN or
replacing that file, pass `--use-existing-pid-list`. This is useful when you
want to force synchronization or accounting for a manually selected PID list.

```bash
d1cn_synchronize.sh [options] <NODE>
```

### d1cn_classify_pids.sh

This script first uses `d1cn_synchronize.sh` to query and compare lists of PIDs from the MN and CN.

Once `d1cn_synchronize.sh` has produced a list of PIDs at `~/force_sync/pid/NODE` that exist
on the MN but not the CN, not all of them necessarily need the heavier `d1cn_force_accounting.sh`
repair. Querying the CN's `/meta` endpoint for each PID distinguishes the two cases by the
wording of the 404 response:

- `No system metadata could be found for given PID: <pid>.` — the object was simply never
  successfully synced, and a plain `d1cn_synchronize.sh --force-sync` is sufficient.
- `No system metadata could be found for given PID: <pid>. The object with the PID has been
  deleted from the node.` — the object is in the purgatory state described above and requires
  `d1cn_force_accounting.sh`.

`d1cn_classify_pids.sh` reads `~/force_sync/pid/NODE` (or `--pid-file`), queries `/meta` for
each PID, and writes `~/force_sync/pid/NODE.sync` and `~/force_sync/pid/NODE.force` accordingly
(PIDs the CN already knows about are dropped; anything that doesn't match either pattern goes
to `~/force_sync/pid/NODE.unknown` for manual review). Pass `--run` to have it immediately
invoke `d1cn_synchronize.sh --use-existing-pid-list --force-sync` against the `.sync` list and
`d1cn_force_accounting.sh` against the `.force` list.

```bash
d1cn_classify_pids.sh [options] <NODE>

# classify, then run each downstream script against its own list
d1cn_classify_pids.sh --run <NODE>
```

### d1cn_repair_chain.sh

Walks the version chain of one PID or SID backwards (`obsoletes`) and forwards (`obsoletedBy`) on the MN, then compares every link's CN system metadata (`obsoletes`, `obsoletedBy`, `seriesId`) with the MN's, which is treated as the source of truth. Broken links are printed and written to `~/force_sync/pid/NODE.walk.report`. It then tries to repair them by re-synchronizing each broken PID and polling the CN `/meta` endpoint (`--wait`, default 60s). With `--fix-db`, links that are still wrong are corrected in the `systemmetadata` table (a dry run that prints the SQL unless `--execute` is also given; run on each CN as a privileged user, after backing up postgres). PIDs with no CN system metadata are reported for `d1cn_force_accounting.sh`.

```bash
d1cn_repair_chain.sh [options] <NODE> <pid_or_sid>
```

### d1cn_repair_mn_chains.py

Scans the MN's paginated `listObjects` and system metadata to find all PIDs
participating in version links, including linked PIDs not returned by the
listing. Each linked PID is compared once against the CN for `obsoletes`,
`obsoletedBy`, and `seriesId`, using the MN as the reference. Missing or
different CN metadata is reported, submitted to `/v2/synchronize`, and
rechecked for up to 60 seconds per PID. This script uses the same
`~/force_sync/token/NODE` token as `d1cn_repair_chain.sh`, and requires
Python 3 with its standard library.

```bash
# Inspect without changing the CN
python3 d1cn_repair_mn_chains.py --no-sync urn:node:UCSB1
# Synchronize discrepancies and check again
python3 d1cn_repair_mn_chains.py --env prod --wait 60 urn:node:UCSB1
```

`--mn-base-url` and `--cn-base-url` override node URLs; `--page-size` controls
listing requests. Exit status is 0 for a matching scan, 1 for unresolved
differences, and 2 for lookup, pagination, or synchronization errors. Errors
are reported explicitly, and metadata that cannot be read is not repaired.
The scan is not a snapshot: changes to the MN during a run may require another
pass. Singleton objects without version links are not compared. No direct
database changes are made; use `d1cn_repair_chain.sh` or
`d1cn_force_accounting.sh` separately for further investigation.

### d1cn_force_accounting.sh

This script reads the `~/force_sync/pid/NODE` file, then uses the PID to query the `guid` field of the `metacat` database's `identifier` table as the `postgres` user to find the values of the `docid` and `rev` fields. It fetches system metadata from the member node, inserts a missing `systemmetadata` row, and synchronizes the `xml_access` allow rules from the member node's access policy. It then finds the object store path using the `docid` and `rev` values and attempts to sync the object to or from the sister CN using `scp`.

To be effective, this script must be run on both CNs, as most likely `systemmetadata` values need to be propagated to both postgres databases, and one CN may not have a metadata object in the metacat object store.

Verification (calling the `/meta` endpoint of each CN to confirm it knows about the object, and that its values match the ones on the MN) is **not** performed automatically as part of this pass, since it can only succeed once *both* CNs have the required `systemmetadata` row and object store entry in place. Run this normal pass on both CNs first, then run the same command with `--verify-only` (on one or both CNs) to check `/meta` for every PID in the list without touching postgres or the object store. Failures from either the normal pass or a `--verify-only` pass are written to `~/force_sync/pid/NODE.err`.

> **WARNING**: Use caution when invoking this script. It attempts to check whether systemmetadata documents exist in the purgatory state described above before modifying them, but it does modify the postgres database directly—circumventing the API rules—meaning that it could cause havoc if something goes wrong. It is highly recommended that you back up your postgres database prior to running this script in case of any issues.

```bash
# as a privileged user (not tested as root)
sudo d1cn_force_accounting.sh [options] <NODE>

# once the above has completed on both sister CNs, verify without mutating anything
d1cn_force_accounting.sh --verify-only [options] <NODE>
```


The fields in the `identifier` table are as follows:

guid | docid | rev

The fields in the `systemmetadata` table are as follows:

guid | serial_version | date_uploaded | rights_holder | checksum | checksum_algorithm | origin_member_node | authoritive_member_node | date_modified | submitter | object_format | size | archived | replication_allowed | number_replicas | obsoletes | obsoleted_by | series_id | media_type | file_name

For each processed PID, the script replaces existing `xml_access` allow rows with the member node's current allow rules, including public access only when explicitly granted. Existing deny rows and the existing permission order are retained. If the member node cannot be reached or its policy is invalid, existing access rows are left unchanged and the PID is reported as an error. The fields in the `xml_access` table are as follows:

guid | accessfileid | principal_name | permission | perm_type | perm_order | begin_time | end_time | ticket_count | subtreeid | startnodeid | endnodeid


### Cross-CN object transfer setup (`--sister-host`/`--sister-user`)

Since this script must sync metacat objects securely between coordinating nodes,
the CNs must be prepareared to transfer objects while maintaining a hardened security
state. This requires some setup in advance in order for an unprivileged user account
to facilitate the transfer and emplacement of objects between metacat object stores.

Metacat object store files under `/var/metacat/documents` are owned by
`tomcat:tomcat`. `d1cn_force_accounting.sh` never connects to the sister CN as
`root` or as `tomcat` — both are refused for security reasons. Instead it expects
an unprivileged, dedicated sync account (default name `cnsync`, override with
`--sister-user` or `SCP_USER`) that can only stage files and invoke a privileged
wrapper script via `sudo`; the wrapper is the sole thing that reads/writes the
object store and restores `tomcat:tomcat` ownership. This keeps the SSH
account fully separated from the live metacat service identity while still
letting ownership be replicated exactly.

One-time setup on each CN:

1. Create the sync account: `useradd -m -s /bin/bash cnsync` (no password
   login; key-based auth only).
2. Generate a dedicated ed25519 key pair for the account running this script
   and install the public key in `cnsync`'s `~/.ssh/authorized_keys`,
   restricted with `no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding`.
3. Install [remote/cn_object_sync.sh](./remote/cn_object_sync.sh) as
   `root:root`, mode `0700`, at `/usr/local/bin/cn_object_sync.sh` on each CN.
4. Create the staging directory once, owned by the sync account:
   `mkdir -p /var/lib/cn_object_sync.sh/staging && chown cnsync:cnsync /var/lib/cn_object_sync.sh/staging && chmod 700 /var/lib/cn_object_sync.sh/staging`.
5. Add a sudoers rule (e.g. `/etc/sudoers.d/cn_object_sync.sh`) restricting
   `cnsync` to only that wrapper's subcommands — see the header comment in
   [remote/cn_object_sync.sh](./remote/cn_object_sync.sh) for the exact rule.

With this in place, pushing an object to the sister CN stages it via `scp`
into `cnsync`'s staging directory, then runs
`sudo /usr/local/sbin/cn_object_sync.sh install DOCID REV` over SSH, which
moves it into `/var/metacat/documents` and sets `tomcat:tomcat` ownership.
Pulling works in reverse via the wrapper's `export`/`cleanup` subcommands.

If you see `sudo: a password is required` / `a terminal is required to read
the password`, the `sudo` invocation isn't matching the `NOPASSWD` rule in
`/etc/sudoers.d/cn_object_sync.sh` — usually because the wrapper's installed
path doesn't exactly match the `Cmnd_Alias` path (both must be
`/usr/local/bin/cn_object_sync.sh`), or the sudoers file wasn't installed at
all. Since the SSH session has no PTY (by design), `sudo` cannot fall back to
an interactive password prompt, so any path mismatch results in this error.

## License
```
Copyright [2026] [Regents of the University of California]

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

## Acknowledgements
Work on this package was supported by:

- DataONE Network
- Arctic Data Center: NSF-PLR grant #2042102 to M. B. Jones, A. Budden, M. Schildhauer, and J. Dozier

Additional support was provided for collaboration by the National Center for Ecological Analysis and Synthesis, a Center funded by the University of California, Santa Barbara, and the State of California.

[![DataONE_footer](https://user-images.githubusercontent.com/6643222/162324180-b5cf0f5f-ae7a-4ca6-87c3-9733a2590634.png)](https://dataone.org)

[![nceas_footer](https://www.nceas.ucsb.edu/sites/default/files/2020-03/NCEAS-full%20logo-4C.png)](https://www.nceas.ucsb.edu)
