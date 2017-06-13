'''
Fabric script to add checks to a target.

This script should be run using fabric, e.g. cd to the folder containing
this file then:

  fab -l

The WATO and user credentials for administration may be set by calling this
srcipt directly.

  python fabfile.py -w <WATO_USER>

or 

  python fabfile.py -s <USER_PASSWD>
  
to set credentials for WATO and user shell accounts respectively.

Credentials are saved in the system keystore: keychain on OS X, credentials
vault on windows, and secretstorage on Linux (configurable). See

  https://pypi.python.org/pypi/keyring

for details on the keyring implementation.

'''
import logging
import os
import requests
import keyring
import json
import fabric
from fabric.api import sudo, env, task

DATAONE_SHELL_KEYRING="DataONE-Credentials"
WATO_URL="https://monitor-unm-1.dataone.org/unm/check_mk/webapi.py"
WATO_AUTOMATION_KEYRING="WATO-Automation"
MRPE_CONFIG_FOLDER = "/etc/check_mk"
MRPE_CONFIG_FILE = os.path.join(MRPE_CONFIG_FOLDER, "mrpe.cfg")
NAGIOS_PLUGINS = "/usr/lib/nagios/plugins"

CHECKS = {'APT_Upgrades': '/usr/lib/nagios/plugins/check_apt',
          'NTP_Time_Basic': '/usr/lib/nagios/plugins/check_ntp_time -H us.pool.ntp.org -w 5 -c 10'}

def checkExists(name):
  if fabric.contrib.files.exists(MRPE_CONFIG_FILE):
    if fabric.contrib.files.contains(MRPE_CONFIG_FILE, "^"+name, escape=False):
      return True
  print("Entry {0} not present".format(name))
  return False


def setupMRPECheck(name, command):
  sudo("mkdir -p /etc/check_mk")
  text = "{0} {1}\n".format(name, command)
  fabric.contrib.files.append(MRPE_CONFIG_FILE, text, use_sudo=True)


@task
def installBasicMonitoring():
  '''
  Install nagios-plugins-basic on host
  '''
  sudo("apt-get install -y nagios-plugins-basic")


def addCheckCommand(name, command):
  if checkExists(name):
    print("Configuration for {0} exists.".format(name))
    return
  setupMRPECheck(name, command)


@task
def enableAllChecks():
  installBasicMonitoring()
  for name in CHECKS.keys():
    addCheckCommand(name, CHECKS[name])


###############################################################################
#== WATO automation part

@task
def watoActivateChanges():
  '''
  Activate pending changes in Wato
  '''
  data = getWatoCredentialsFromKeyring()
  data['action'] = 'activate_changes'
  data['mode'] = 'dirty'
  data['request'] = '{}'
  result = requests.post(WATO_URL, data)
  print(result.text)


@task
def watoDiscoverServices():
  '''
  Asks Wato to do a service discovery operation for the host
  '''
  host = env.host_string
  data = getWatoCredentialsFromKeyring()
  data['action'] = 'discover_services'
  data['request'] = json.dumps({"hostname": host})
  result = requests.post(WATO_URL, data)
  print(result.text)


@task
def addChecksInventoryCommit():
  '''
  Adds all checks to the host, does an inventory, and commits the change
  '''
  creds = getDataONECredentialsFromKeyring()
  env.password = creds['passwd']
  enableAllChecks()
  watoDiscoverServices()
  watoActivateChanges()


###############################################################################
# Credential management
def setKeyringCredential(service_name, user, passwd):
  '''
  Set username and password under well-known entry in keyring
  
  Set username and password in well-known location that is user independent. 

    service_name: ID = user
    service_name: user = passwd
    
  In this way the username to use for the service can always be retrieved, 
  otherwise it would be necessary to always request the username as input.

  Args:
    service_name: Name of service 
    user:  Name of user 
    passwd: Password

  '''
  logging.info("Set credentials in service %s for %s", service_name, user)
  keyring.set_password(service_name,"ID", user)
  keyring.set_password(service_name, user, passwd)


def getKeyringCredential(service_name):
  '''
  Retrieve the username and password for the specified service.

  Args:
    service_name: name of service

  Returns:
    dict of "user" and "passwd"
  '''
  logging.info("Get credential for service: %s", service_name)
  uid = {}
  uid['user'] = keyring.get_password(service_name,"ID")
  uid['passwd'] = keyring.get_password(service_name, uid['user'])
  return uid


def setDataONECredentialsInKeyring(user, passwd):
  setKeyringCredential(DATAONE_SHELL_KEYRING, user, passwd)


def getDataONECredentialsFromKeyring():
  logging.info("Get credentials for service: %s", DATAONE_SHELL_KEYRING)
  return getKeyringCredential(DATAONE_SHELL_KEYRING)


def setWatoCredentialsInKeyring(user, passwd):
  setKeyringCredential(WATO_AUTOMATION_KEYRING, user, passwd)


def getWatoCredentialsFromKeyring():
  # use keys expected by WATO HTTP API
  _uid = getKeyringCredential(WATO_AUTOMATION_KEYRING)
  uid['_username'] = _uid['user']
  uid['_secret'] = _uid['passwd']
  return uid


# Optional, set credentials in keyring
if __name__ == "__main__":
  import argparse
  import getpass
  parser = argparse.ArgumentParser(description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument('-l', '--log_level',
                      action='count',
                      default=0,
                      help='Set logging level, multiples for more detailed.')
  parser.add_argument('-s', '--shell',
                      default=None,
                      help="Set shell account for DataONE")
  parser.add_argument('-w', '--wato',
                      default=None,
                      help="Set wato account monitor-unm-1.dataone.org")
  args = parser.parse_args()
  levels = [logging.WARNING, logging.INFO, logging.DEBUG]
  level = levels[min(len(levels) - 1, args.log_level)]
  logging.basicConfig(level=level,
                      format="%(asctime)s %(levelname)s %(message)s")
  if args.shell is not None:
    username = args.shell
    passwd = getpass.getpass("Password for shell user {0}:".format(username))
    setDataONECredentialsInKeyring(username, passwd)
  elif args.wato is not None:
    username = args.wato
    passwd = getpass.getpass("Password for wato user {0}:".format(username))
    setDataONECredentialsInKeyring(username, passwd)
  #Display user names set for shell and wato
  uid = getDataONECredentialsFromKeyring()
  print("Shell user = {user}".format(**uid))
  uid = getWatoCredentialsFromKeyring()
  print("Wato user = {_username}".format(**uid))