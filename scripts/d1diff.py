#!/usr/bin/env python

import argparse
import collections
import datetime
import logging
import multiprocessing
import sys

import requests

import d1_client.iter.objectlist as objectlistiterator
import d1_client.mnclient_1_1
import d1_client.mnclient_2_0
import d1_client.cnclient_2_0
import d1_client.solr_client
import d1_common.const

# Check for discrepancies between MN and CN by comparing object lists

ENV_DICT = {
  'prod': {
    'name': 'Production',
    'base_url': d1_common.const.URL_DATAONE_ROOT,
    'host': 'cn.dataone.org',
    'solr_base': '/cn/v1/query/solr/',
  },
  'stage': {
    'name': 'Stage',
    'base_url': 'https://cn-stage.test.dataone.org/cn',
    'host': 'cn-stage.test.dataone.org',
    'solr_base': '/cn/v1/query/solr/',
  },
  'sandbox': {
    'name': 'Sandbox',
    'base_url': 'https://cn-sandbox.test.dataone.org/cn',
    'host': 'cn-sandbox.test.dataone.org',
    'solr_base': '/cn/v1/query/solr/',
  },
  'dev': {
    'name': 'Development',
    'base_url': 'https://cn-dev.test.dataone.org/cn',
    'host': 'cn-dev.test.dataone.org',
    'solr_base': '/cn/v1/query/solr/',
  },
}

# Default maximum number of identifiers to print
MAX_PRINT_PIDS = 10
OBJECT_LIST_PAGE_SIZE = 1000


def main():
  logging.basicConfig(level=logging.WARN)
  requests.packages.urllib3.disable_warnings()

  parser = argparse.ArgumentParser(
    description='Show status of synchronization and indexing for a MN'
  )
  parser.add_argument(
    '--env', type=str, default='prod',
    help='Environment, one of {}'.format(', '.join(ENV_DICT))
  )
  parser.add_argument(
    '--cert-pub', dest='cert_pem_path', action='store', default=None,
    help='path to PEM formatted public key of certificate'
  )
  parser.add_argument(
    '--cert-key', dest='cert_key_path', action='store', default=None,
    help='path to PEM formatted private key of certificate'
  )
  parser.add_argument(
    '--max', type=int, default=MAX_PRINT_PIDS,
    help='Maximum number of objects to list. -1 = no limit'
  )
  parser.add_argument(
    '--page-size', type=int, default=OBJECT_LIST_PAGE_SIZE,
    help='Number of objects to retrieve in each call'
  )
  parser.add_argument(
    '--nodes', action='store_true',
    help='List the nodes in the environment and exit'
  )
  parser.add_argument(
    '--count', action='store_true',
    help='List object count for each node in the environment and exit'
  )
  parser.add_argument(
    '--all', action='store_true',
    help='Create report for all the MNs in the environment'
  )
  parser.add_argument(
    'nodeid', type=str, nargs='?', default=None,
    help='MN Node ID (full or any part, case insensitive)'
  )
  args = parser.parse_args()

  try:
    compare(args)
  except CompareError as e:
    print u'Error: {}'.format(e.message)
    sys.exit(1)
  except KeyboardInterrupt:
    print u'Exit'
    sys.exit(1)


def compare(args):
  if args.env not in ENV_DICT:
    raise CompareError(
      u'Environment must be one of {}'.format(', '.join(ENV_DICT))
    )

  env_dict = ENV_DICT[args.env]
  cn_base_url = env_dict['base_url']
  cn_client = d1_client.cnclient_2_0.CoordinatingNodeClient_2_0(
    cn_base_url,
    cert_pem_path=args.cert_pem_path,
    cert_key_path=args.cert_key_path,
  )

  if args.nodes:
    return print_nodes(cn_client, env_dict, cn_base_url)

  if args.count:
    return print_node_counts(cn_client, env_dict, cn_base_url)

  if args.all:
    return compare_all(args, env_dict, cn_client, cn_base_url)

  if args.nodeid is None:
    raise CompareError(
      u'Must supply a MN Node ID (full or any part, case insensitive)'
    )

  return compare_one(args, args.nodeid, env_dict, cn_client, cn_base_url)


def compare_all(args, env_dict, cn_client, cn_base_url):
  for node_pyxb in nodeListIterator(cn_client):
    try:
      compare_one(
        args, node_pyxb.identifier.value(), env_dict, cn_client, cn_base_url
      )
    except StandardError as e:
      logging.exception(e.message)


def compare_one(args, node_id, env_dict, cn_client, cn_base_url):
  print u'Collecting information...'.format(env_dict['name'])

  n_max_identifiers = args.max if args.max != -1 else None

  # CN
  cn_node_pyxb = find_node(
    cn_client, cn_base_url, base_url=env_dict['base_url']
  )
  if cn_node_pyxb is None:
    raise CompareError(u'CN Node ID not found on {}'.format(cn_base_url))
  cn_node_id = cn_node_pyxb.identifier.value()

  # MN
  mn_node_pyxb = find_node(cn_client, cn_base_url, node_id_search_str=node_id)
  if mn_node_pyxb is None:
    raise CompareError(
      u'No match for MN Node ID search "{}" found on {}'.
      format(node_id, cn_base_url)
    )
  mn_node_id = mn_node_pyxb.identifier.value()
  if mn_node_pyxb.type != 'mn':
    raise CompareError(
      u'MN Node ID "{}" is a {}. Must be a MN'.
      format(mn_node_id, mn_node_pyxb.type.upper())
    )
  mn_base_url = mn_node_pyxb.baseURL

  print_header(env_dict, cn_node_pyxb, mn_node_pyxb)
  cn_pid_dict, n_cn_objects = get_object_dict(
    cn_node_id, cn_client, args.page_size, mn_node_id
  )
  major_version_int = find_node_version(mn_node_pyxb)
  assert major_version_int in (1, 2)
  if major_version_int == 1:
    mn_client = d1_client.mnclient_1_1.MemberNodeClient_1_1(
      mn_base_url,
      cert_pem_path=args.cert_pem_path,
      cert_key_path=args.cert_key_path,
    )
  else:
    mn_client = d1_client.mnclient_2_0.MemberNodeClient_2_0(
      mn_base_url,
      cert_pem_path=args.cert_pem_path,
      cert_key_path=args.cert_key_path,
    )
  mn_pid_dict, n_mn_objects = get_object_dict(
    mn_node_id, mn_client, args.page_size
  )
  n_solr_records = count_solr_records(env_dict, mn_node_id)

  print
  print '-' * 80
  print
  print u'Environment: {}\n'.format(env_dict['name'])
  print_header(env_dict, cn_node_pyxb, mn_node_pyxb)
  print u'\n{}: Total number of objects: {:n} (from {})'.format(
    cn_node_id, n_cn_objects, mn_node_id
  )
  print u'{}: Total number of objects: {:n}'.format(mn_node_id, n_mn_objects)
  print_unique(
    mn_node_id, cn_node_id, mn_pid_dict, cn_pid_dict, n_max_identifiers
  )
  print_unique(
    cn_node_id, mn_node_id, cn_pid_dict, mn_pid_dict, n_max_identifiers
  )
  print u'\n{}: Solr index records for {}: {:n}'.format(
    cn_node_id, mn_node_id, n_solr_records
  )


def print_header(env_dict, cn_node_pyxb, mn_node_pyxb):
  print u'{}: CN @ {}'.format(
    cn_node_pyxb.identifier.value(), cn_node_pyxb.baseURL
  )
  print u'{}: MN @ {}'.format(
    mn_node_pyxb.identifier.value(), mn_node_pyxb.baseURL
  )


def print_nodes(client, env_dict, cn_base_url):
  print 'Nodes registered in {} @ {}:'.format(env_dict['name'], cn_base_url)
  for node_pyxb in nodeListIterator(client):
    print u'  {}: {} @ {}'.format(
      node_pyxb.identifier.value(), node_pyxb.type.upper(), node_pyxb.baseURL
    )


def print_node_counts(client, env_dict, cn_base_url, cert_pem_path, cert_key_path):
  print u'Total objects for nodes registered in {} @ {}:'.format(
    env_dict['name'], cn_base_url
  )
  for node_pyxb in nodeListIterator(client):
    mn_client = d1_client.mnclient_1_1.MemberNodeClient_1_1(node_pyxb.baseURL,    cert_pem_path=cert_pem_path,
    cert_key_path=cert_key_path,
)
    try:
      count_str = "{:,}".format(get_object_count(mn_client))
    except d1_common.types.exceptions.DataONEException as e:
      s = e.description.replace('\n', ' ')
      if len(s) > 50:
        s = u'{}...'.format(s[:50])
      count_str = u'{}: {}'.format(e.name, s)
    except StandardError as e:
      count_str = e.message
    print u'  {}: {} @ {}: {}'.format(
      node_pyxb.identifier.value(),
      node_pyxb.type.upper(), node_pyxb.baseURL, count_str
    )


def find_node(cn_client, display_str, node_id_search_str=None, base_url=None):
  print u'{}: Searching NodeList for "{}"...'.format(
    display_str, node_id_search_str if node_id_search_str else base_url
  )
  for node_pyxb in nodeListIterator(cn_client):
    if (node_id_search_str and node_id_search_str.lower() in node_pyxb.identifier.value().lower()) \
        or node_pyxb.baseURL == base_url:
      return node_pyxb


def find_node_version(node_pyxb):
  major_version_list = []
  for s in node_pyxb.services.service:
    major_version_list.append(int(s.version[1:]))
  return max(major_version_list)


def get_object_dict(
    node_id_display_str,
    client,
    page_size,
    node_id_filter_str=None,
):
  n_objects = get_object_count(client, node_id_filter_str)
  pid_dict = {}
  start_time = datetime.datetime.now()

  object_list_iterator = ObjectListIterator(
    client, node_id=node_id_filter_str, page_size=page_size
  ).object_list()

  # object_list_iterator = MultiprocessObjectListIterator(
  #   base_url, node_id=node_id_filter_str
  # ).object_list()

  for i, object_info in enumerate(object_list_iterator):
    pid_dict[object_info.identifier.value()] = object_info
    if (datetime.datetime.now() - start_time).seconds > 1.0 or i == n_objects - 1:
      start_time = datetime.datetime.now()
      print u'{}: Retrieving ObjectList{}: {:.2f}% ({:,}/{:,})'.format(
        node_id_display_str, u' for {}'.format(node_id_filter_str)
        if node_id_filter_str else u'', (i + 1) / float(n_objects) * 100.0,
        i + 1, n_objects
      )
  return pid_dict, n_objects


def get_object_count(client, node_id_filter_str=None):
  return client.listObjects(nodeId=node_id_filter_str, count=0).total


def print_unique(
    this_node_id, other_node_id, this_dict, other_dict, n_max_identifiers=None
):
  only_pid_set = set(this_dict.keys()).difference(set(other_dict.keys()))
  print
  if not len(this_dict):
    print u'{}: Has NO objects'.format(this_node_id)
  elif not len(only_pid_set):
    print u'{}: Has {} objects, all of which are on {}'.format(
      this_node_id, len(this_dict), other_node_id
    )
  else:
    print u'{}: Has {} objects that are not on {}'.format(
      this_node_id, len(only_pid_set), other_node_id
    )
  if n_max_identifiers and len(only_pid_set) > n_max_identifiers:
    print u'{}: First {} objects:'.format(this_node_id, n_max_identifiers)
  elif len(only_pid_set):
    print u'{}: All {} objects:'.format(this_node_id, len(only_pid_set))
  for pid_str in sorted(
      only_pid_set, key=lambda x: this_dict[x].dateSysMetadataModified
  )[:n_max_identifiers]:
    print u'{}:  pid="{}" dateSysMetadataModified="{}"'.format(
      this_node_id, pid_str, this_dict[pid_str].dateSysMetadataModified
    )


def count_solr_records(env_dict, node_id):
  solr_client = d1_client.solr_client.SolrConnection(
    host=env_dict['host'], solrBase=env_dict['solr_base']
  )
  return solr_client.count(
    q=u'datasource:{}'.format(solr_client.escapeQueryTerm(node_id))
  )


class CompareError(Exception):
  pass


class ObjectListIterator(object):
  LIST_OBJECTS_PAGE_SIZE = 1000

  def __init__(
      self, client, node_id=None, object_format=None, replica_status=None,
      current_start=0, page_size=LIST_OBJECTS_PAGE_SIZE
  ):
    self._client = client
    self._node_id = node_id
    self._object_format = object_format
    self._replica_status = replica_status
    self._current_start = current_start
    self._page_size = page_size

  def object_list(self):
    while True:
      try:
        object_list = self._client.listObjects(
          start=self._current_start,
          count=self._page_size,
          nodeId=self._node_id,
          objectFormat=self._object_format,
          replicaStatus=self._replica_status,
        )
      except StandardError as e:
        #pass
        #logging.exception(e.message)
        #print self._client.last_response_body
        #raise
        continue
      else:
        logging.debug(
          'Retrieved page: {}/{}'.format(
            self._current_start / self._page_size + 1, object_list.total / self._page_size
          )
        )

      for d1_object in object_list.objectInfo:
        yield d1_object

      self._current_start += object_list.count
      if self._current_start >= object_list.total:
        break


class MultiprocessObjectListIterator(object):
  LIST_OBJECTS_PAGE_SIZE = 1000

  def __init__(
      self, base_url, node_id=None, object_format=None, replica_status=None,
      current_start=0, page_size=LIST_OBJECTS_PAGE_SIZE
  ):
    self._base_url = base_url
    self._node_id = node_id
    self._object_format = object_format
    self._replica_status = replica_status
    self._current_start = current_start
    self._page_size = page_size

    self._pool = multiprocessing.Pool(processes=10)
    self._deque = collections.deque(maxlen=1000)

  def object_list(self):
    self._fill()

    while True:
      for d1_object in self._deque:
        yield d1_object

  def _fill(self):
    client = d1_client.cnclient_2_0.CoordinatingNodeClient_2_0(self._base_url)
    total = client.listObjects(count=0).total
    num_pages = total / self._page_size

    for page_idx in range(num_pages):
      object_list = self._pool.apply_async(self._getPage, (self, page_idx,))
      print object_list.get(timeout=10 * 60)
      #self._deque.extend(object_list.get(timeout=10 * 60))

  def _getPage(self, page_idx):
    try:
      object_list = self._client.listObjects(
        start=page_idx * self._page_size,
        count=self._page_size,
        nodeId=self._node_id,
        objectFormat=self._object_format,
        replicaStatus=self._replica_status,
      )
    except StandardError as e:
      logging.exception(e.message)
    else:
      logging.debug(
        'Retrieved page: {}/{}'.format(
          self._current_start / self._page_size + 1, object_list.total / self._page_size
        )
      )
      return "test"
      # return object_list.objectInfo.toxml()


def nodeListIterator(client):
  try:
    node_list_pyxb = client.listNodes()
  except StandardError as e:
    logging.exception(e.message)
    raise
  else:
    logging.debug(
      'Retrieved {} Node documents'.format(len(node_list_pyxb.node))
    )
  for node_pyxb in sorted(
      node_list_pyxb.node, key=lambda x: x.identifier.value()
  ):
    yield node_pyxb


if __name__ == '__main__':
  multiprocessing.freeze_support()
  main()
