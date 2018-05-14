'''
CRUD operations on protected node properties.

IMPORTANT:
  This script won't work without a direct or tunnelled connection to a CN
  LDAP server. e.g.:

    ssh -L3890:localhost:389 cn-dev-ucsb-1.test.dataone.org

  LDAP will then be available on port 3890 on your machine.

Protected node properties are set directly in the node document store (i.e. LDAP) on the CN and are not updated by changes to a Member Node node document.

Protected node properties are all key, value entries that appear in the node document Properties element with a key prefix of "CN_"

Example: add an entry:

  dn: d1NodePropertyId=CN_logo_url_2,cn=urn:node:mnDemo6,dc=dataone,dc=org
  changetype: add
  objectClass: top
  objectClass: d1NodeProperty
  d1NodeId: urn:node:mnDemo6
  d1NodePropertyId: CN_logo_url_2
  d1NodePropertyKey: CN_logo_url
  d1NodePropertyValue: https://raw.github.com

Example: delete an entry:

dn: d1NodePropertyId=CN_logo_url_2,cn=urn:node:mnDemo6,dc=dataone,dc=org
changetype: delete

Example: find node properties for NodeID:

  ldapsearch -H ldap://localhost -D cn=admin,dc=dataone,dc=org -w PASSWORD \
   -b "cn=urn:node:mnDemo6,dc=dataone,dc=org" \
   -s one -a always -z 1000 -LLL \
   "(objectClass=d1NodeProperty)"

Python ldap examples:

  http://www.grotan.com/ldap/python-ldap-samples.html
'''

import logging
from pprint import pprint
import ldap
from ldap import modlist
from d1_admin_tools.operations import expandNodeID

# The list of protected node properties
ALLOWED_PROPERTIES = [
  'CN_node_name',
  'CN_operational_status',
  'CN_date_operational',
  'CN_date_upcoming',
  'CN_date_deprecated',
  'CN_logo_url',
  'CN_info_url',
  'CN_location_lonlat',     #longitude,latitude WGS84, same order as WKT POINT
]


def getLDAPConnection(host="ldap://localhost:3890",
                      bind_dn="cn=admin,dc=dataone,dc=org", 
                      password=None):
  con = ldap.initialize(host)
  if password is None:
    password = ''
  con.simple_bind( bind_dn, password )
  return con


def _readEntryValue(entry, field):
  props = {}
  try:
    props = entry[1]
  except IndexError as e:
    logging.info("No properties in provided entry.")
    return None
  try:
    pval = props[field]
  except KeyError as e:
    logging.info("Property %s no present", field)
    return None
  if isinstance(pval, list):
    if len(pval) == 1:
      return pval[0]
  return pval


# ====== CRUD operations =========

def createNodeProperty(con, node_id, key, value):
  '''Add a property specified by key, value
  
  Note: Need to be careful that the node_id case is exactly right, otherwise the
  java deserializer doesn't seem to find the property that was added.
  '''
  if key not in ALLOWED_PROPERTIES:
    raise KeyError("key must be one of {0}".format( \
       ",".join(ALLOWED_PROPERTIES)))
  property_id = key
  node_id = expandNodeID(node_id)
  dn = "d1NodePropertyId={0},cn={1},dc=dataone,dc=org".format(property_id, node_id)
  logging.debug("DN = %s", dn)
  entry = {'objectClass': ['top', 'd1NodeProperty'],
           'd1NodeId': node_id,
           'd1NodePropertyId': property_id,
           'd1NodePropertyKey': key,
           'd1NodePropertyValue': value,
          }
  add_record = modlist.addModlist(entry)
  pprint( add_record )
  con.add_s(dn, add_record)


def readNodeProperty(con, node_id, key):
  '''Return a list of (DN,
                       d1NodePropertyId, 
                       d1NodePropertyKey, 
                       d1NodePropertyValue) 
  that match the provided node_id and key.
  
  Note that you can use a "*" to return all properties for node_id.
  '''
  result = []
  node_id = expandNodeID(node_id)
  dn = "cn={0},dc=dataone,dc=org".format(node_id)
  q = "(&(objectClass=d1NodeProperty)(d1NodePropertyKey={0}))".format(key)
  logging.debug("Filter = %s", q)
  attrs = [
    'd1NodePropertyId',
    'd1NodePropertyKey',
    'd1NodePropertyValue']
  res = con.search_s(dn, ldap.SCOPE_SUBTREE, q, attrs )
  for entry in res:
    row = (entry[0], 
           _readEntryValue(entry, 'd1NodePropertyId'),
           _readEntryValue(entry, 'd1NodePropertyKey'),
           _readEntryValue(entry, 'd1NodePropertyValue')
           )
    result.append(row)
  return result


def updateNodeProperty(con, node_id, key, value, old_value=None):
  '''Update existing node property  
  '''
  if key not in ALLOWED_PROPERTIES:
    raise KeyError("key must be one of {0}".format( \
       ",".join(ALLOWED_PROPERTIES)))
  property_id = key
  node_id = expandNodeID(node_id)
  if old_value is None:
    res = readNodeProperty(con, node_id, key)
    old_value = res[0][3]
  dn = "d1NodePropertyId={0},cn={1},dc=dataone,dc=org".format(property_id, node_id)
  logging.debug("DN = %s", dn)
  old_entry = {'d1NodePropertyValue': old_value}
  entry = {'d1NodePropertyValue': value}
  mod_record = modlist.modifyModlist(old_entry, entry)
  pprint( mod_record )
  return con.modify_s(dn, mod_record)


def deleteNodeProperty(con, node_id, key):
  '''Delete a node property.
  
  Raises ldap.NO_SUCH_OBJECT if not present
  '''
  property_id = key
  node_id = expandNodeID(node_id)
  dn = "d1NodePropertyId={0},cn={1},dc=dataone,dc=org".format(property_id, node_id)
  logging.debug("DELETE: %s", dn)
  return con.delete_s(dn)


def createOrUpdateNodeProperty(con, node_id, key, value):
  '''Update the specified node property or create if not present
  '''
  res = readNodeProperty(con, node_id, key)
  if len(res) == 0:
    if value is None:
      # A null value deletes, but there's nothing to delete
      return None
    return createNodeProperty(con, node_id, key, value)
  if value is None:
    return deleteNodeProperty(con, node_id, key)
  return updateNodeProperty(con, node_id, key, value, old_value=res[0][3])


def listNodes(con, attrs=None):
  '''Retrieve a list of all node_ids by examining LDAP
  '''
  result = []
  dn = "dc=dataone,dc=org"
  q = "(&(objectClass=d1Node)(d1NodeType=mn))"
  if attrs is None:
    attrs = ['d1NodeId']
  res = con.search_s(dn, ldap.SCOPE_SUBTREE, q, attrs)
  for entry in res:
    if len(attrs) == 1:
      result.append(_readEntryValue(entry, attrs[0]))
    else:
      row = []
      for attr in attrs:
        row.append(_readEntryValue(entry, attr)) 
      result.append(row)
  return result


def listAllNodeProperties(con):
  '''Retrieve a list of custom properties for all nodes.
  '''
  nodes = listNodes(con)
  result = {}
  for node in nodes:
    props = readNodeProperty(con, node, "*")
    entry = {}
    for k in ALLOWED_PROPERTIES:
      entry[k] = None
    for prop in props:
      if prop[2].startswith("CN_"):
        entry[prop[2]] = prop[3]
    result[node] = entry
  return result


def setNodesProperties(con, nodes_properties):
  '''Given a dict of:
    {node_id: {property: value,
               property: value}
      }
  Call createOrUpdateNodeProperty for each entry.
  '''
  for node_id in list(nodes_properties.keys()):
    properties = nodes_properties[node_id]
    for key in list(properties.keys()):
      logging.info("%s set prop %s to %s", node_id, key, str(properties[key]))
      createOrUpdateNodeProperty(con, node_id, key, properties[key])


if __name__ == "__main__":
  import sys
  import getpass
  import yaml
  logging.basicConfig(level=logging.INFO)
  print('''
Make sure you have an LDAP connection on port 3890 by doing something like:

  ssh -L3890:localhost:389 cn-dev-ucsb-1.test.dataone.org
  ''')
  passwd = getpass.getpass("What's the LDAP password: ")
  con = getLDAPConnection(password=passwd)
  print(( yaml.dump(listAllNodeProperties(con), default_flow_style=False, explicit_start=True) ))
  sys.exit(0)
  
  node_id = eval(input("Node ID: "))
  res = readNodeProperty(con, node_id, "*")
  dn = node_id
  if len(res) > 0:
    dn = res[0][0]
  print("----")
  print(("Properties set on {0}:".format(dn)))
  print(("  {0:15}  {1} ".format("Key","Value")))
  for entry in res:
    print(("  {0:15}  {1}".format(entry[2], entry[3])))
