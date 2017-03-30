'''


'''

import os
import logging
import time
from getpass import getpass
from StringIO import StringIO
from fabric.api import sudo, get, put, run
from fabric.context_managers import env


def expandNodeID(nodeId):
  '''Add urn:node: to start of nodeID if not present.
  '''
  if nodeId.startswith('urn:node:'):
    return nodeId
  return "urn:node:" + nodeId


def escapeSolrQueryTerm(term):
  '''
  + - && || ! ( ) { } [ ] ^ " ~ * ? : \
  '''
  reserved = ['+', '-', '&', '|', '!', '(', ')', '{', '}',
              '[', ']', '^', '"', '~', '*', '?', ':',
              ]
  term = term.replace(u'\\', u'\\\\')
  for c in reserved:
    term = term.replace(c, u"\%s" % c)
  return term


def tmpFileName(tmp_dir="/tmp", prefix="", ext="txt"):
  '''
  Returns a temporary file name with a high likelihood of uniqueness.

  :param tmp_dir: Folder to contain the file
  :param prefix: Prefix for file name
  :param ext: Extension for file name (not including the .)
  :return: File name and path relative to tmp_dir.
  '''
  ts = int(time.time()*100000)
  return os.path.join(tmp_dir, "{0}_{1}.{2}".format(prefix, ts, ext))


#=======================
#== Fabric Operations ==

def listCNClientCertificates():
  '''List the contents of /etc/dataone/client/private
  '''
  cmd = "ls -la /etc/dataone/client/private"
  sudo(cmd)


def getCNClientCertificate(cert_file_name):
  '''Retrieve the client certificate + key combination from the host.

  The file is retrieved and placed in ~/.dataone/certificates/<host name>

  Attributes:
    cert_file_name (str): Name of the certificate file located under
        /etc/dataone/client/private to be retrieved.
  '''
  host_name = env.host_string
  target_folder = os.path.join(os.path.expanduser('~'), ".dataone/certificates/{0}".format(host_name))
  if not os.path.exists(target_folder):
    os.makedirs(target_folder, 0700)
  target_file = os.path.join(target_folder, cert_file_name)
  if os.path.exists(target_file):
    print("The certificate file already exists: {0}. Rename or remove to download a new copy.".format(target_file))
    return
  source_file = os.path.join("/etc/dataone/client/private/", cert_file_name)
  get(source_file, target_file, use_sudo=True)


def setNodeSynchronize(node_id, state, ldap_pass=None):
  '''Adjust the LDAP entry for the specified node to indicate if node should be synchronized

  Attributes:
    node_id (str): The node entry to adjust
    state (str): Either "up" or "down"
  '''
  node_id = expandNodeID(node_id)
  state = state.lower()
  if state not in ("up", "down"):
    raise ValueError("State must be 'up' or 'down'")
  if ldap_pass is None:
    ldap_pass = getpass("Enter LDAP password: ")
  ldiff = StringIO()
  ldiff.write("dn: cn={0},dc=dataone,dc=org\n".format(node_id))
  ldiff.write("changetype: modify\n")
  ldiff.write("replace: d1NodeState\n")
  ldiff.write("d1NodeState: {0}\n".format(state));
  remote_file = "nodeupdate.ldiff"
  put(ldiff, remote_file)
  cmd = "cat " + remote_file + "; "
  cmd += "ldapmodify -H ldap://localhost -D cn=admin,dc=dataone,dc=org "
  cmd += " -w '{0}' ".format(ldap_pass)
  cmd += " -f {0}".format(remote_file)
  run(cmd)


def setNodeState(node_id, state, ldap_pass=None):
  '''Adjust the LDAP entry for the specified node to indicate if node is online.

  Attributes:
    node_id (str): The node entry to adjust
    state (str): Either "up" or "down"
  '''
  node_id = expandNodeID(node_id)
  state = state.lower()
  if state not in ("up", "down"):
    raise ValueError("State must be 'up' or 'down'")
  if ldap_pass is None:
    ldap_pass = getpass("Enter LDAP password: ")
  ldiff = StringIO()
  ldiff.write("dn: cn={0},dc=dataone,dc=org\n".format(node_id))
  ldiff.write("changetype: modify\n")
  ldiff.write("replace: d1NodeState\n")
  ldiff.write("d1NodeState: {0}\n".format(state));
  remote_file = "nodeupdate.ldiff"
  put(ldiff, remote_file)
  cmd = "cat " + remote_file + "; "
  cmd += "ldapmodify -H ldap://localhost -D cn=admin,dc=dataone,dc=org "
  cmd += " -w '{0}' ".format(ldap_pass)
  cmd += " -f {0}".format(remote_file)
  run(cmd)


def approveNode(node_id, ldap_pass=None, approval=False):
  '''Adjust the LDAP entry for a node, indicating if approved or not.

  Attributes:
    node_id (str): The node entry to adjust
    approval (bool): True or False
  '''
  node_id = expandNodeID(node_id)
  state = str(approval).upper()
  if state not in ("TRUE", "FALSE"):
    raise ValueError("State must be 'TRUE' or 'FALSE'")
  if ldap_pass is None:
    ldap_pass = getpass("Enter LDAP password: ")
  ldiff = StringIO()
  ldiff.write("dn: cn={0},dc=dataone,dc=org\n".format(node_id))
  ldiff.write("changetype: modify\n")
  ldiff.write("replace: d1NodeApproved\n")
  ldiff.write("d1NodeApproved: {0}\n".format(state));
  remote_file = "nodeupdate.ldiff"
  put(ldiff, remote_file)
  cmd = "cat " + remote_file + "; "
  cmd += "ldapmodify -H ldap://localhost -D cn=admin,dc=dataone,dc=org "
  cmd += " -w '{0}' ".format(ldap_pass)
  cmd += " -f {0}".format(remote_file)
  run(cmd)


def resetNodeHarvestDate(node_id, ldap_pass=None, harvest_timestamp="1900-01-01T00:00:00Z"):
  '''Reset the last harvest date for a MN.
  '''
  node_id = expandNodeID(node_id)
  if ldap_pass is None:
    ldap_pass = getpass("Enter LDAP password: ")
  ldiff = StringIO()
  ldiff.write("dn: cn={0},dc=dataone,dc=org\n".format(node_id))
  ldiff.write("changetype: modify\n")
  ldiff.write("replace: d1NodeLastHarvested\n")
  ldiff.write("d1NodeLastHarvested: {0}\n".format(harvest_timestamp));
  remote_file = "nodeupdate.ldiff"
  put(ldiff, remote_file)
  cmd = "cat " + remote_file + "; "
  cmd += "ldapmodify -H ldap://localhost -D cn=admin,dc=dataone,dc=org "
  cmd += " -w '{0}' ".format(ldap_pass)
  cmd += " -f {0}".format(remote_file)
  run(cmd)


def resetNodeLogAggregationDate(node_id, ldap_pass=None, harvest_timestamp="1900-01-01T00:00:00Z"):
  '''Reset the last log aggregation harvest date for a MN.
  '''
  node_id = expandNodeID(node_id)
  if ldap_pass is None:
    ldap_pass = getpass("Enter LDAP password: ")
  ldiff = StringIO()
  ldiff.write("dn: cn={0},dc=dataone,dc=org\n".format(node_id))
  ldiff.write("changetype: modify\n")
  ldiff.write("replace: d1NodeLogLastAggregated\n")
  ldiff.write("d1NodeLogLastAggregated: {0}\n".format(harvest_timestamp));
  remote_file = "nodeupdate.ldiff"
  put(ldiff, remote_file)
  cmd = "cat " + remote_file + "; "
  cmd += "ldapmodify -H ldap://localhost -D cn=admin,dc=dataone,dc=org "
  cmd += " -w '{0}' ".format(ldap_pass)
  cmd += " -f {0}".format(remote_file)
  run(cmd)


#========================
#== CRUD on MN custom properties


#========================
#== DataONE Operations ==


def resolve(client, pid):
  ''' Resolve the provided identifier in the specified environment

  :param client: An instance of CoordinatingNodeClient
  :param pid: Identifier to resolve
  :return: Dictionary mimicking an objectLocationList with addition of error entry
  '''
  logger = logging.getLogger('main')
  response = {'status':{},
              'xml': None,
              }
  try:
    res = client.resolveResponse(pid)
    obj_locs = client._read_dataone_type_response(
      res, 'ObjectLocationList', response_is_303_redirect=True
    )
    response['status']['msg'] = 'OK'
    response['status']['code'] = res.status_code
    response['xml'] = res.content #dom.toprettyxml(indent="  ")
    response['identifier'] = unicode(obj_locs.identifier.value())
    response['id_is_sid'] = not (pid == response['identifier'])
    response['objectLocation'] = []
    for loc in obj_locs.objectLocation:
      oloc = {'url': unicode(loc.url),
              'nodeIdentifier': unicode(loc.nodeIdentifier.value()),
              'baseURL': unicode(loc.baseURL),
              'version': map(unicode, loc.version),
              'preference': unicode(loc.preference) }
      response['objectLocation'].append(oloc)
  except Exception as e:
    logger.info(e)
    response['status']['msg'] = unicode(e)
    #response['status']['code'] = e.errorCode
  return response