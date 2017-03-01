
import logging
import hashlib
from d1_client import cnclient_1_1, cnclient_2_0, mnclient_2_0, mnclient_1_1

#==============================

class Node(object):
  '''
  A wrapper around a DataONE Node description instance.
  '''

  def __init__(self, node):
    '''
    Initialize with an instance of a Node Description

    :param node: instance of https://releases.dataone.org/online/api-documentation-v2.0/apis/Types2.html#v2_0.Types.Node
    '''
    self._L = logging.getLogger(self.__class__.__name__)
    self._node = node
    self._client = None
    self.kw_hash = ""


  def getBaseURL(self):
    '''
    Get the baseURL of this node

    :return: URL
    '''
    return self._node.baseURL


  def isCN(self):
    '''
    Return True if this node is a Coordinating Node

    :return: boolean
    '''
    return self._node.type.lower() == 'cn'


  def isMN(self):
    '''
    Return True if this node is a Member Node

    :return: boolean
    '''
    return self._node.type.lower() == 'mn'


  def isV2(self, require_write=False):
    '''
    Return True if node is version 2 for read, or if require_write, for writing.

    :param require_write:
    :return: boolean
    '''
    if self.isCN():
      name_to_check = 'cnread'
    else:
      if require_write:
        name_to_check = 'mnstorage'
      else:
        name_to_check = 'mnread'
    for service in self._node.services.service:
      if service.name.lower() == name_to_check:
        if service.version.lower() == 'v2':
          return service.available
    return False


  def getClient(self, force_new=False, **kwargs):
    '''
    Factory method to return an instance of a DataONE client that can be used to interact with the node.

    Clients are re-used if already created unless force_new is specified.

    :param force_new:
    :return: instance of class derived from BaseClient
    '''
    cls = None
    is_v2 = self.isV2()
    base_url = self.getBaseURL()
    if self.isCN():
      if is_v2:
        cls = cnclient_2_0.CoordinatingNodeClient_2_0
      else:
        cls = cnclient_1_1.CoordinatingNodeClient_1_1
    else:
      if is_v2:
        cls = mnclient_2_0.MemberNodeClient_2_0
      else:
        cls = mnclient_1_1.MemberNodeClient_1_1
    if not kwargs.has_key('allow_redirects'):
      kwargs['allow_redirects'] = False
    hsh = hashlib.sha256()
    hsh.update( unicode(kwargs) )
    kw_hash = hsh.hexdigest()
    self._L.debug("Existing hash = %s", self.kw_hash)
    self._L.debug("New hash = %s", kw_hash)
    if self._client is not None:
      self._L.debug("client exists")
      if isinstance(self._client, cls):
        if self._client._base_url == base_url:
          if self.kw_hash == kw_hash:
            if not force_new:
              self._L.debug("reusing existing client")
              return self._client
        else:
          self._L.debug("client base url differs: %s vs. %s", self._client._base_url, base_url)
    self._L.debug("Creating {0} for baseURL {1}".format(cls.__name__, base_url))
    self.kw_hash = hsh.hexdigest()
    self._client = cls(base_url, **kwargs)
    return self._client


#==============================

class Nodes(object):
  '''
  Wrapper around the set of nodes present in an environment.

  '''

  def __init__(self, base_url):
    '''
    Initialize the node list instance. The nodes are not loaded until load() is called.

    :param base_url: The base URL of the primary node in the environment, e.g. https://cn.dataone.org/cn
    '''
    self._L = logging.getLogger(self.__class__.__name__)
    if base_url is None:
      base_url = "https://cn.dataone.org/cn"
    self.base_url = base_url
    self.primary_node_id = None
    self.client = None
    self.nodes = {}


  def __unicode__(self):
    return u"\n".join(self.nodes.keys())


  def getNode(self, node_id=None):
    '''
    Retrieve the node instance identified by the provided node_id or the primary node if node_id is not specified.

    Calling this method will trigger retrieval of the node list from the primary node if it has not already been done.

    :param node_id: NodeId of the node to retrieve, or None for the primary node.
    :return: instance of Node or None
    '''
    if len(self.nodes.keys()) < 1:
      self.load()
    if node_id is None:
      node_id = self.primary_node_id
    try:
      return self.nodes[node_id]
    except KeyError as e:
      self._L.warn("NodeID '{0}' not in node list".format(node_id))
    return None


  def getNodeBaseURL(self, node_id):
    node = self.getNode(node_id)
    if node is None:
      return None
    return node.getBaseURL()


  def getClient(self, node_id=None, force_new=False, **kwargs):
    '''

    :param node_id:
    :param force_new:
    :param kwargs: dictionary of optional settings that will be passed on to the client constructor.
    :return:
    '''
    node = self.getNode(node_id)
    if node is None:
      raise ValueError("NodeID '{0}' not present in node list".format(node_id))
    return node.getClient(force_new=force_new, **kwargs)


  def load(self, **kwargs):
    '''
    Load the nodes from the base_url provided in the Nodes constructor.

    :return: nothing
    '''
    client = cnclient_2_0.CoordinatingNodeClient_2_0(self.base_url, allow_redirects=False, **kwargs)
    nodes = client.listNodes()
    self.nodes = {}
    for node in nodes.node:
      anode = Node(node)
      node_id = node.identifier.value()
      self.nodes[node_id] = anode
      if anode.getBaseURL() == self.base_url:
        self.primary_node_id = node_id
        anode._client = client
        if not kwargs.has_key('allow_redirects'):
          kwargs['allow_redirects'] = False
        hsh = hashlib.sha256()
        hsh.update(unicode(kwargs))
        anode.kw_hash = hsh.hexdigest()


#==============================

if __name__ == "__main__":
  nodes = Nodes("https://cn.dataone.org/cn")
  nodes.load()
  print(unicode(nodes))
