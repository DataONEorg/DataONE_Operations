#!/usr/bin/env python3

# Check for discrepancies between MN and CN by comparing object lists

import argparse
import datetime
import logging
import multiprocessing
import sys

import d1_client.iter.node
import d1_client.iter.objectlist_multi

import d1_client.mnclient_1_1
import d1_client.mnclient_2_0
import d1_client.cnclient_2_0
import d1_client.solr_client

import d1_common.const
import d1_common.types.exceptions
import d1_common.env

# Default maximum number of identifiers to print
MAX_PRINT_PIDS = 10
OBJECT_LIST_PAGE_SIZE = 1000
API_MAJOR=2

def main():
  logging.basicConfig(level=logging.WARN)

  parser = argparse.ArgumentParser(
    description='Show status of synchronization and indexing for a MN'
  )
  parser.add_argument(
    '--env', type=str, default='prod',
    help='Environment, one of {}'.format(', '.join(d1_common.env.D1_ENV_DICT))
  )
  parser.add_argument(
    '--cert-pub', dest='cert_pem_path', action='store', default=None,
    help='Path to PEM formatted public key of certificate'
  )
  parser.add_argument(
    '--cert-key', dest='cert_key_path', action='store', default=None,
    help='Path to PEM formatted private key of certificate'
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
    '--api-major', type=int, default=API_MAJOR,
    help='DataONE API major version (1 or 2)'
  )
  parser.add_argument(
    'nodeid', type=str, nargs='?', default=None,
    help='MN Node ID (full or any part, case insensitive)'
  )
  args = parser.parse_args()

  try:
    compare(args)
  except CompareError as e:
    print('Error: {}'.format((str(e))))
    sys.exit(1)
  except KeyboardInterrupt:
    print('Exit')
    sys.exit(1)


def compare(args):
  if args.env not in d1_common.env.D1_ENV_DICT:
    raise CompareError(
      'Environment must be one of {}'.format(
        ', '.join(d1_common.env.D1_ENV_DICT)
      )
    )

  env_dict = d1_common.env.D1_ENV_DICT[args.env]
  cn_base_url = env_dict['base_url']
  cn_client = d1_client.cnclient_2_0.CoordinatingNodeClient_2_0(
    cn_base_url,
    cert_pem_path=args.cert_pem_path,
    cert_key_path=args.cert_key_path,
  )

  if args.nodes:
    return print_nodes(cn_client, env_dict, cn_base_url)

  if args.count:
    return print_node_counts(
      cn_client, env_dict, cn_base_url, args.cert_pem_path, args.cert_key_path
    )

  if args.all:
    return compare_all(args, env_dict, cn_client, cn_base_url)

  if args.nodeid is None:
    raise CompareError(
      'Must supply a MN Node ID (full or any part, case insensitive)'
    )

  return compare_one(args, args.nodeid, env_dict, cn_client, cn_base_url)


def compare_all(args, env_dict, cn_client, cn_base_url):
  for node_pyxb in d1_client.iter.node.NodeListIterator(cn_client):
    try:
      compare_one(
        args, node_pyxb.identifier.value(), env_dict, cn_client, cn_base_url
      )
    except Exception as e:
      logging.exception((str(e)))


def compare_one(args, node_id, env_dict, cn_client, cn_base_url):
  print('Collecting information...'.format(env_dict['name']))

  n_max_identifiers = args.max if args.max != -1 else None

  # CN

  cn_node_pyxb = find_node(
    cn_base_url, env_dict['base_url']
  )
  if cn_node_pyxb is None:
    raise CompareError('CN Node ID not found on {}'.format(cn_base_url))
  cn_node_id = cn_node_pyxb.identifier.value()

  # MN

  mn_node_pyxb = find_node(cn_base_url, node_id)
  if mn_node_pyxb is None:
    raise CompareError(
      'No match for MN Node ID search "{}" found on {}'.format(
        node_id, cn_base_url
      )
    )
  mn_node_id = mn_node_pyxb.identifier.value()
  if mn_node_pyxb.type != 'mn':
    raise CompareError(
      'MN Node ID "{}" is a {}. Must be a MN'.format(
        mn_node_id, mn_node_pyxb.type.upper()
      )
    )

  mn_base_url = mn_node_pyxb.baseURL

  print_header(cn_node_pyxb, mn_node_pyxb)

  client_args_dict = {
    'cert_pem_path': args.cert_pem_path,
    'cert_key_path': args.cert_key_path,
  }

  cn_pid_dict, n_cn_objects = get_object_dict(
    cn_base_url, args.page_size, args.api_major, client_args_dict,
    list_objects_args_dict={
      'nodeId': mn_node_id
    },
    node_id_display_str=cn_node_id,
    node_id_filter_str=mn_node_id,
  )

  major_version_int = find_node_version(mn_node_pyxb)

  assert major_version_int in (1, 2)

  mn_pid_dict, n_mn_objects = get_object_dict(
    mn_base_url, args.page_size, major_version_int, client_args_dict,
    {},
    node_id_display_str=mn_node_id,
    node_id_filter_str=None,
  )

  # client_args_dict = client_args_dict, list_objects_args_dict = list_objects_args_dict,

  n_solr_records = count_solr_records(cn_base_url, mn_node_id)

  print()
  print('-' * 80)
  print()
  print('Environment: {}\n'.format(env_dict['name']))
  print_header(cn_node_pyxb, mn_node_pyxb)
  print(
    '\n{}: Total number of objects: {:n} (from {})'.format(
      cn_node_id, n_cn_objects, mn_node_id
    )
  )
  print('{}: Total number of objects: {:n}'.format(mn_node_id, n_mn_objects))
  print_unique(
    mn_node_id, cn_node_id, mn_pid_dict, cn_pid_dict, n_max_identifiers
  )
  print_unique(
    cn_node_id, mn_node_id, cn_pid_dict, mn_pid_dict, n_max_identifiers
  )
  print(
    '\n{}: Solr index records for {}: {:n}'.format(
      cn_node_id, mn_node_id, n_solr_records
    )
  )


def print_header(cn_node_pyxb, mn_node_pyxb):
  print(
    '{}: CN @ {}'.format(cn_node_pyxb.identifier.value(), cn_node_pyxb.baseURL)
  )
  print(
    '{}: MN @ {}'.format(mn_node_pyxb.identifier.value(), mn_node_pyxb.baseURL)
  )


def print_nodes(client, env_dict, cn_base_url):
  print('Nodes registered in {} @ {}:'.format(env_dict['name'], cn_base_url))
  for node_pyxb in d1_client.iter.node.NodeListIterator(client):
    print(
      '  {}: {} @ {}'.format(
        node_pyxb.identifier.value(), node_pyxb.type.upper(), node_pyxb.baseURL
      )
    )


def print_node_counts(
    client, env_dict, cn_base_url, cert_pem_path, cert_key_path
):
  print(
    'Total objects for nodes registered in {} @ {}:'.format(
      env_dict['name'], cn_base_url
    )
  )
  for node_pyxb in d1_client.iter.node.NodeListIterator(client):
    mn_client = d1_client.mnclient_1_1.MemberNodeClient_1_1(
      node_pyxb.baseURL,
      cert_pem_path=cert_pem_path,
      cert_key_path=cert_key_path,
    )
    try:
      count_str = "{:,}".format(get_object_count(mn_client))
    except d1_common.types.exceptions.DataONEException as e:
      s = e.description.replace('\n', ' ')
      if len(s) > 50:
        s = '{}...'.format(s[:50])
      count_str = '{}: {}'.format(e.name, s)
    except Exception as e:
      count_str = (str(e))
    print(
      '  {}: {} @ {}: {}'.format(
        node_pyxb.identifier.value(), node_pyxb.type.upper(), node_pyxb.baseURL,
        count_str
      )
    )


def find_node(cn_base_url, find_str):
  print(
    '{}: Searching NodeList for "{}"...'.format(cn_base_url, find_str)
  )
  for node_pyxb in d1_client.iter.node.NodeListIterator(cn_base_url):
    if (
      find_str.lower() in node_pyxb.identifier.value().lower() or
      find_str.lower() in node_pyxb.baseURL.lower()
    ):
      return node_pyxb


def find_node_version(node_pyxb):
  major_version_list = []
  for s in node_pyxb.services.service:
    major_version_list.append(int(s.version[1:]))
  return max(major_version_list)


def get_object_dict(
    base_url,
    page_size,
    api_major,
    client_args_dict,
    list_objects_args_dict,
    node_id_display_str,
    node_id_filter_str=None,
):
  pid_dict = {}
  last_status_time = datetime.datetime.now()

  object_list_iterator = d1_client.iter.objectlist_multi.ObjectListIteratorMulti(
    base_url,
    page_size,
    api_major=api_major,
    client_args_dict=client_args_dict,
    list_objects_args_dict=list_objects_args_dict,
  )

  n_objects = object_list_iterator.total

  for i, object_info in enumerate(object_list_iterator):
    pid_dict[object_info.identifier.value()] = object_info
    if (datetime.datetime.now() -
        last_status_time).seconds > 1.0 or i == n_objects - 1:
      last_status_time = datetime.datetime.now()
      print(
        '{}: Retrieving ObjectList{}: {:.2f}% ({:,}/{:,})'.format(
          node_id_display_str, ' for {}'.format(node_id_filter_str)
          if node_id_filter_str else '', (i + 1) / float(n_objects) * 100.0,
          i + 1, n_objects
        )
      )
  return pid_dict, n_objects


def get_object_count(client, node_id_filter_str=None):
  return client.listObjects(nodeId=node_id_filter_str, count=0).total


def print_unique(
    this_node_id, other_node_id, this_dict, other_dict, n_max_identifiers=None
):
  only_pid_set = set(this_dict.keys()).difference(set(other_dict.keys()))
  print()
  if not len(this_dict):
    print('{}: Has NO objects'.format(this_node_id))
  elif not len(only_pid_set):
    print(
      '{}: Has {} objects, all of which are on {}'.format(
        this_node_id, len(this_dict), other_node_id
      )
    )
  else:
    print(
      '{}: Has {} objects that are not on {}'.format(
        this_node_id, len(only_pid_set), other_node_id
      )
    )
  if n_max_identifiers and len(only_pid_set) > n_max_identifiers:
    print('{}: First {} objects:'.format(this_node_id, n_max_identifiers))
  elif len(only_pid_set):
    print('{}: All {} objects:'.format(this_node_id, len(only_pid_set)))
  for pid_str in sorted(
      only_pid_set,
      key=lambda x: this_dict[x].dateSysMetadataModified)[:n_max_identifiers]:
    print(
      '{}:  pid="{}" dateSysMetadataModified="{}"'.format(
        this_node_id, pid_str, this_dict[pid_str].dateSysMetadataModified
      )
    )


def count_solr_records(base_url, node_id):
  solr_client = d1_client.solr_client.SolrClient(base_url)
  return solr_client.count(
    q='datasource:{}'.format(solr_client._prepare_query_term('datasource', node_id))
  )


class CompareError(Exception):
  pass


if __name__ == '__main__':
  multiprocessing.freeze_support()
  main()
