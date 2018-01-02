LetsEncrypt Certificates
========================


See also [[Connectivity and Certificates|CN_connectivity]]

.. contents:: 
   :local:

Install Certbot
---------------

Install the ``cerbot`` tool to generate LetsEncrypt certificates.

See [[LetsEncrypt]] for installation details.


Adjust ``node.properties``
--------------------------

Two additional properites need to be added to ``/etc/dataone/node.properties``:

====================== ===============
Key                    Description 
====================== ===============
``environment.hosts``  Space delimited list of host names for CNs participating in the environment 
``cn.rsyncuser``       Username of account to use when syncing content across CNs. 
====================== ===============


For example, on ``cn-stage-ucsb-1.test.dataone.org``:

.. code-block:: properties

  environment.hosts=cn-stage-ucsb-1.test.dataone.org cn-stage-unm-1.test.dataone.org cn-stage-orc-1.test.dataone.org
  cn.rsyncuser=rsync_user

Prepare for Verification
------------------------

Before running the certificate generation command it is necessary to create the working folder that will be used for the verifications. Do the following on each CN:

.. code-block:: bash

  PROPERTIES="/etc/dataone/node.properties"
  RSUSER=$(grep "^cn.rsyncuser=" ${PROPERTIES} | cut -d'=' -f2)
  sudo mkdir -p /var/www/.well-known/acme-challenge
  sudo chown -R ${RSUSER}:${RSUSER} /var/www/.well-known/acme-challenge
  sudo setfacl -Rdm g:${RSUSER}:rw /var/www/.well-known/acme-challenge/
  sudo chmod g+s /var/www/.well-known/acme-challenge/

Apache must be configured to not redirect the verification address in the ``.well-known`` folder. The following example is for ``cn-stage-ucsb-1.test.dataone.org``. Adjust ``ServerName``, ``ServerAlias``, and ``RedirectMatch`` with appropriate values for the respective environment and host:

.. code-block:: apache

  <VirtualHost *:80>
    ###
    # This config only comes into play when DNS for cn-stage.test.dataone.org
    # is pointing to this server
    ###
    ServerName cn.dataone.org
    ServerAlias cn-stage-ucsb-1.dataone.org
    ServerAdmin administrator@dataone.org
    DocumentRoot /var/www/
    ErrorLog ${APACHE_LOG_DIR}/error.log
    CustomLog ${APACHE_LOG_DIR}/access.log combined

    # Redirect all traffic except certbot to HTTPS
    RedirectMatch ^/(?!.well-known)(.*) https://cn-stage.test.dataone.org/$1
  </VirtualHost>


Supporting Scripts
------------------

The certificate generation process relies on the following authentication and cleanup hooks to copy verification information to other nodes participating in the environment and to cleanup afterwards.

``/etc/letsencrypt/renewal/manual-auth-hook.sh``:

.. code-block:: bash

  #!/bin/bash
  PROPERTIES="/etc/dataone/node.properties"
  RSUSER=$(grep "^cn.rsyncuser=" ${PROPERTIES} | cut -d'=' -f2)
  HOSTS=$(grep "^environment.hosts=" ${PROPERTIES} | cut -d'=' -f2)
  THIS_HOST=$(hostname -f)
  FNVALID="/var/www/.well-known/acme-challenge/$CERTBOT_TOKEN"
  CREDS="/home/${RSUSER}/.ssh/id_rsa"
  echo $CERTBOT_VALIDATION > ${FNVALID}
  for TARGET_HOST in ${HOSTS}; do
    if [ "${TARGET_HOST}" != "${THIS_HOST}" ]; then
      echo "Copying verification to ${TARGET_HOST}"
      scp -i ${CREDS} ${FNVALID} ${RSUSER}@${TARGET_HOST}:${FNVALID}
    fi
  done

``/etc/letsencrypt/renewal/manual-cleanup-hook.sh``:

.. code-block:: bash

  #!/bin/bash
  PROPERTIES="/etc/dataone/node.properties"
  RSUSER=$(grep "^cn.rsyncuser=" ${PROPERTIES} | cut -d'=' -f2)
  HOSTS=$(grep "^environment.hosts=" ${PROPERTIES} | cut -d'=' -f2)
  THIS_HOST=$(hostname -f)
  FNVALID="/var/www/.well-known/acme-challenge/$CERTBOT_TOKEN"
  CREDS="/home/${RSUSER}/.ssh/id_rsa"
  rm ${FNVALID}
  for TARGET_HOST in ${HOSTS}; do
    if [ "${TARGET_HOST}" != "${THIS_HOST}" ]; then
      echo "Removing verification from ${TARGET_HOST}"
      ssh -i ${CREDS} ${RSUSER}@${TARGET_HOST} "rm ${FNVALID}"
    fi
  done

After a certificate is renewed, it is necessary to notify administrators that some action is required. Place the following `notify-administrators.sh` in the `renew-hook.d` folder. Any scripts in that folder will be called on a successful certificate renewal.

.. code-block:: bash

  #!/bin/bash
  PROPERTIES="/etc/dataone/node.properties"
  THIS_HOST=$(hostname -f)
  THIS_ENVIRONMENT=$(grep "^cn.router.hostname=" ${PROPERTIES} | cut -d'=' -f2)
  ADMIN="administrator@dataone.org"

  cat <<EOF | mail -s "Certificate Renewal on ${THIS_ENVIRONMENT}" ${ADMIN}
  Hi! 
  certbot running on ${THIS_HOST} has generated a new server certificate for the
  ${THIS_ENVIRONMENT} environment.

  Some manual steps must be taken to complete the installation of the new
  certificate. The process for this is documented at:

    https://github.com/DataONEorg/DataONE_Operations/wiki/LetsEncrypt-CNs
    
  but basically entails running:

    /etc/letsencrypt/renewal/post-cn-cert-renew.sh

  then restarting services on each CN in the ${THIS_ENVIRONMENT} environment.

  cheers
  EOF


Account for Synchronization
---------------------------

- Create account, disable password
- Create ssh keys
- Distribute ssh public keys
- Verify ssh to other hosts
- Enable rsync for account


Certificate Generation
----------------------

The server certificate must have a primary subject of the primary CN name and must also include as subject alternative names the host names of each CN participating in the environment. For example, the stage environment would include: ``cn-stage.test.dataone.org``, ``cn-stage-ucsb-1.test.dataone.org``, ``cn-stage-orc-1.test.dataone.org``, and ``cn-stage-unm-1.test.dataone.org``.

Certificate generation is performed by ``certbot`` with the following command run on the primary host only (remove the ``--dry-run`` parameter to do an actual request)::

  PROPERTIES="/etc/dataone/node.properties"
  HOSTS=$(grep "^environment.hosts=" ${PROPERTIES} | cut -d'=' -f2)
  THIS_ENVIRONMENT=$(grep "^cn.router.hostname=" ${PROPERTIES} | cut -d'=' -f2)
  DOMAINS="-d ${THIS_ENVIRONMENT}"
  for DHOST in ${HOSTS}; do DOMAINS="${DOMAINS} -d ${DHOST}"; done

  sudo certbot certonly --dry-run --manual \
    --preferred-challenges=http \
    --manual-auth-hook=/etc/letsencrypt/renewal/manual-auth-hook.sh \
    --manual-cleanup-hook=/etc/letsencrypt/renewal/manual-cleanup-hook.sh \
    --cert-name ${THIS_ENVIRONMENT} ${DOMAINS}

After a successful first time certificate generation, is is necessary to configure various services to use the new certificates. This procedure should only need to be done once.


Adjust Apache Configuration
---------------------------

Apache HTTPS configuration is straight forward::

  <VirtualHost *:443>
    ServerName cn.dataone.org
    # Change the following for the respective host
    ServerAlias cn-ucsb-1.dataone.org  
    ...

    SSLCACertificateFile /etc/ssl/certs/DataONECAChain.crt

    SSLCertificateKeyFile  /etc/letsencrypt/live/cn.dataone.org/privkey.pem
    SSLCertificateFile  /etc/letsencrypt/live/cn.dataone.org/fullchain.pem
    SSLCertificateChainFile /etc/letsencrypt/lets-encrypt-x3-cross-signed.pem
  </VirtualHost>


Adjust Postgres Certificate References
--------------------------------------

``Postgres`` is configured to use the server certificate and expects the certificate and key to be located in ``/var/lib/postgresql/9.3/main/`` (Note that "9.3" is the current version of postgres installed. The actual location may change in the future).

Symbolic links may be used to refer to the actual certificate location. Replace the existing ``server.crt`` and ``server.key`` for postgress with::

  PROPERTIES="/etc/dataone/node.properties"
  THIS_ENVIRONMENT=$(grep "^cn.router.hostname=" ${PROPERTIES} | cut -d'=' -f2)
  CERTS="/etc/letsencrypt/live/${THIS_ENVIRONMENT}"
  sudo mv /var/lib/postgresql/9.3/main/server.crt "/var/lib/postgresql/9.3/main/server.crt.$(date +%Y%m%d)"
  sudo mv /var/lib/postgresql/9.3/main/server.key "/var/lib/postgresql/9.3/main/server.key.$(date +%Y%m%d)"
  sudo ln -s "${CERTS}/cert.pem" /var/lib/postgresql/9.3/main/server.crt
  sudo ln -s "${CERTS}/privkey.pem" /var/lib/postgresql/9.3/main/server.key

The linked files will survive a refresh of the certificates, so this only needs to be done once.


Configure the DataONE Portal Application
----------------------------------------

- portal.properties
- set permissions
- restart tomcat


Certificate Renewal
-------------------

LetsEncrypt certificates are relatively short lived (three months), so an automated mechanism to check and update the certificates is needed. Since restarting services on the DataONE Coordinating Nodes requires some coordination across the servers, this process is not yet entirely automated, though all that should be necessary is for an administrator to execute a script to distribute the certificate and then manually restart services on each CN. Basically:

1. ``certbot`` generates a new certificate from a ``cron`` job
2. DataONE administrators are notified of the need for action
3. An administrator distributes the certificate to each CN
4. An administrator restarts services as necessary

The certificate renewal process is performed by ``cron`` using the task ``/etc/cron.weekly/certbot-renew`` listed below::

  #!/bin/bash
  set -e
  logger "Checking for LetsEncrypt certificate renewal"
  /usr/bin/certbot renew -n --quiet \
    --renew-hook "/bin/run-parts /etc/letsencrypt/renew-hook.d/"

The tasks in ``/etc/letsencrypt/renew-hook.d/`` are executed when certificates are successfully renewed. For the CNs, a successful renewal results in a notification being sent to administrators requesting that the next steps of the
certificate renewal are followed.

The following script will ensure the certificates have the correct permissions and synchronize the certificates to other servers using rsync.

``/etc/letsencrypt/renewal/post-cn-cert-renew.sh``::

  #!/bin/bash
  PROPERTIES="/etc/dataone/node.properties"
  RSUSER=$(grep "^cn.rsyncuser=" ${PROPERTIES} | cut -d'=' -f2)
  HOSTS=$(grep "^environment.hosts=" ${PROPERTIES} | cut -d'=' -f2)
  THIS_HOST=$(hostname -f)
  THIS_ENVIRONMENT=$(grep "^cn.router.hostname=" ${PROPERTIES} | cut -d'=' -f2)

  function synchronize_certs() {
    logger "INFO: Synchronizing letsencrypt certificates to other CNs..."
    #Set permissions for ssl-cert group access
    echo "Setting permissions on certificates..."
    chgrp -R ssl-cert /etc/letsencrypt/archive
    chmod g+rx /etc/letsencrypt/archive
    chgrp -R ssl-cert /etc/letsencrypt/live
    chmod g+rx /etc/letsencrypt/live
    #This is needed for Postgres to start:
    chmod 0640 /etc/letsencrypt/archive/${THIS_ENVIRONMENT}/privkey*

    #Synchronize with other servers
    for TARGET_HOST in ${HOSTS}; do
      if [ "${TARGET_HOST}" != "${THIS_HOST}" ]; then
        echo "Syncing certificate info to ${TARGET_HOST}"
        rsync -avu --rsync-path="/home/${RSUSER}/bin/rsync-wrapper.sh" \
          -e "ssh -i /home/${RSUSER}/.ssh/id_rsa -l ${RSUSER}" \
          /etc/letsencrypt/*  \
          ${RSUSER}@${TARGET_HOST}:/etc/letsencrypt/
      fi
    done
  }

  echo "Using variables:"
  echo "RSUSER = ${RSUSER}"
  echo "HOSTS = ${HOSTS}"
  echo "THIS_HOST = ${THIS_HOST}"
  echo "THIS_ENVIRONMENT = ${THIS_ENVIRONMENT}"
  echo
  read -p "Does this look OK (y/N)?" -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    synchronize_certs
    exit 0
  fi
  echo "Aborted."



Service Restarts
----------------

After a new certificate has been distributed it is necessary to restart ``apache2``, ``postgresql``, and ``tomcat7`` to pick up the change::

  # Verify apache configuration is OK
  sudo apache2ctl -t
  sudo service apache2 restart
  sudo service postgres restart


TODO: refer to procedure for tomcat restart on CNs


Verification
------------

Verification that the new certificate basically comes down to three checks: 

1. Check service is running

  * Is the service running?
  
    ::

      sudo service apache2 status
      sudo service postgres status
      sudo service tomcat7 status

  * Is a listener on the expected port?

    ::
  
      sudo netstat -tulpn

2. Verify the new certificate is being used

   The following command run from the command line will show the certificate being used by the server in its plain text form::
   
     TARGET="cn-ucsb-1.dataone.org:443"
     echo "Q" | openssl s_client -connect ${TARGET} | openssl x509 -text -noout

3. Verify that a client can connect as expected

   Use a web browser to check the server responds as expected. Use a DataONE client to interact with the server.

