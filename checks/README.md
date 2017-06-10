# README `/checks`
Contains various `check_mk` checks for DataONE Coordinating Nodes,
Member Nodes, and Operations servers.

## Local Checks

### General

Unless otherwise specified, these `check_*` scripts should be placed in
`/usr/lib/check_mk_agent/local` and made executable.

Verify operation by executing the sript, then log in to the monitor and
from `Wato`, select the host and "Save & go to Services" to verify the
new checks show up. Choose to activate the new services and save the
configuration.

[Local checks](http://mathias-kettner.com/checkmk_localchecks.html)
are executed by `check-_mk-agent` and provide output that is aggregated
and forwarded back to the monitor host.

### Installation

Drop the check into `/usr/lib/check_mk_agent/local` and make the check
executable. Verify operation by executing the check from the command
line and examining the output.


## Nagios Plugins

Before creating a local check, see if the desired functionality is
already available with a nagios plugin. These are installed along
with `check-mk-agent` and are installed in `/usr/lib/nagios/plugins`.

These plugins are executed using
[MRPE](http://mathias-kettner.com/checkmk_mrpe.html) and are enabled by
adding entries to `/etc/check_mk/mrpe.cfg` (create the folder and file
if it does not exist).

### NTP Time

```
NTP_Time_Basic  /usr/lib/nagios/plugins/check_ntp_time -H us.pool.ntp.org -w 5 -c 10
```

