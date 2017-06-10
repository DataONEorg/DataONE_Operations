'''
Fabric script to add checks to a target.
'''
import logging
import os
import requests
import keyring
import json
import fabric
from fabric.api import run, sudo, put, parallel, get, env, task, settings

DATAONE_AUTOMATION_KEYRING="DataONE-Credentials"
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


#== WATO automation part

def setDataONECredentialsInKeyring(user, passwd):
  logging.info("Setting keyring credentials for {0}".format(user))
  keyring.set_password(DATAONE_AUTOMATION_KEYRING,"ID", user)
  keyring.set_password(DATAONE_AUTOMATION_KEYRING, user, passwd)


def getDataONECredentialsFromKeyring():
  uid = {}
  uid['user'] = keyring.get_password(DATAONE_AUTOMATION_KEYRING,"ID")
  uid['passwd'] = keyring.get_password(DATAONE_AUTOMATION_KEYRING, uid['user'])
  return uid


def setWatoCredentialsInKeyring(user, passwd):
  logging.info("Setting keyring credentials for {0}".format(user))
  keyring.set_password(WATO_AUTOMATION_KEYRING,"ID", user)
  keyring.set_password(WATO_AUTOMATION_KEYRING, user, passwd)


def getWatoCredentialsFromKeyring():
  uid = {}
  uid['_username'] = keyring.get_password(WATO_AUTOMATION_KEYRING,"ID")
  uid['_secret'] = keyring.get_password(WATO_AUTOMATION_KEYRING, uid['_username'])
  return uid


@task
def watoActivateChanges():
  '''
  Activate pending changes in wato
  Returns:
  '''
  data = getWatoCredentialsFromKeyring()
  data['action'] = 'activate_changes'
  data['mode'] = 'dirty'
  data['request'] = '{}'
  result = requests.post(WATO_URL, data)
  print(result.text)


@task
def watoDiscoverServices():
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
  Returns:

  '''
  creds = getDataONECredentialsFromKeyring()
  env.password = creds['passwd']
  enableAllChecks()
  watoDiscoverServices()
  watoActivateChanges()
