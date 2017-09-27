#!/usr/bin/env python

import argparse
import logging
import sys

import d1_client.cnclient_1_1
import d1_client.cnclient_2_0
import d1_client.iter.node
import d1_client.mnclient_1_1
import d1_client.mnclient_2_0
import d1_common.checksum
import d1_common.env
import d1_common.node
import d1_common.object_format
import d1_common.types.exceptions
import d1_common.url
import d1_common.xml


TIMEOUT_SEC = 30 * 60


def main():
  parser = argparse.ArgumentParser(
    description='Attempt to retrieve replias and display results'
  )
  parser.add_argument(
    '--env', type=str, default='prod',
    help='Environment, one of {}'.format(', '.join(d1_common.env.D1_ENV_DICT))
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
    '--timeout', action='store', default=TIMEOUT_SEC,
    help='amount of time to wait for calls to complete (seconds)'
  )
  parser.add_argument(
    '--use-v1', action='store_true', default=False,
    help='use the v1 API (v2 is default)'
  )
  parser.add_argument(
    '--debug', action='store_true', default=False, help='debug level logging'
  )
  parser.add_argument(
    'pid', nargs='+', help='list of PIDs to audit'
  )

  args = parser.parse_args()

  log_setup(is_debug=args.debug)

  try:
    d1env_dict = d1_common.env.D1_ENV_DICT[args.env]
  except LookupError:
    raise AuditError(
      'Environment must be one of {}'.format(', '.join(D1_ENV_DICT))
    )

  if args.use_v1:
    mn_client_cls = d1_client.mnclient_1_1.MemberNodeClient
    cn_client_cls = d1_client.cnclient_1_1.CoordinatingNodeClient_1_1
  else:
    mn_client_cls = d1_client.mnclient_2_0.MemberNodeClient_2_0
    cn_client_cls = d1_client.cnclient_2_0.CoordinatingNodeClient_2_0

  for pid in args.pid:
    audit_replicas(
      cn_client_cls, mn_client_cls, d1env_dict, pid, args.cert_pem_path,
      args.cert_key_path
    )


def audit_replicas(
  cn_client_cls, mn_client_cls, d1env_dict, pid, cert_pem_path, cert_key_path
):
  cn_client = cn_client_cls(
    d1env_dict['base_url'],
    cert_pem_path=cert_pem_path,
    cert_key_path=cert_key_path,
  )

  logging.info('-' * 100)
  logging.info('PID: {}'.format(pid))

  try:
    sysmeta_pyxb = cn_client.getSystemMetadata(pid)
  except d1_common.types.exceptions.DataONEException as e:
    logging.error(
      'Unable to retrieve SysMeta from CN. error="{}"'.format(e.name)
    )
    return

  algo_str = sysmeta_pyxb.checksum.algorithm
  node_dict = get_node_dict(cn_client)

  for replica_pyxb in sysmeta_pyxb.replica:
    replica_mn_id = replica_pyxb.replicaMemberNode.value()
    logging.info('{}:'.format(replica_mn_id))
    mn_client = mn_client_cls(
      node_dict[replica_mn_id]['base_url'],
      cert_pem_path=cert_pem_path,
      cert_key_path=cert_key_path,
    )
    mn_sysmeta_checksum_str = get_sysmeta_checksum_str(mn_client, pid)
    logging.info('  SysMeta: {}'.format(mn_sysmeta_checksum_str))
    mn_obj_checksum_str = calc_obj_checksum_str(mn_client, pid, algo_str)
    logging.info('  Obj:     {}'.format(mn_obj_checksum_str))


def log_setup(is_debug=False):
  formatter = logging.Formatter(
    '%(asctime)s %(levelname)-8s %(message)s', '%Y-%m-%d %H:%M:%S'
  )
  console_logger = logging.StreamHandler(sys.stderr)
  console_logger.setFormatter(formatter)
  logging.getLogger('').addHandler(console_logger)
  logging.getLogger('').setLevel(logging.DEBUG if is_debug else logging.INFO)


def get_node_dict(cn_client):
  return d1_common.node.pyxb_to_dict(cn_client.listNodes())


def calc_obj_checksum_str(client, pid, algo_str):
  try:
    checksum_pyxb = calc_obj_checksum_pyxb(client, pid, algo_str)
  except d1_common.types.exceptions.DataONEException as e:
    return e.name
  except Exception as e:
    return e.message
  else:
    return d1_common.checksum.format_checksum(checksum_pyxb)


def get_sysmeta_checksum_str(client, pid):
  try:
    sysmeta_pyxb = client.getSystemMetadata(pid)
  except d1_common.types.exceptions.DataONEException as e:
    return e.name
  except Exception as e:
    return e.message
  else:
    return d1_common.checksum.format_checksum(sysmeta_pyxb.checksum)


def calc_obj_checksum_pyxb(client, pid, algo_str):
  sciobj_iter = client.get(pid)
  return d1_common.checksum.create_checksum_object_from_iterator(
    sciobj_iter, algo_str
  )


class AuditError(Exception):
  pass


if __name__ == '__main__':
  main()
