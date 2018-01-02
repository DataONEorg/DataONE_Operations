Virtual Machine Setup
=====================


Kernel Purging
--------------

``/etc/cron.daily/purge-old-kernels``::

  #!/bin/bash
  /usr/local/bin/purge_old_kernels.py -q




