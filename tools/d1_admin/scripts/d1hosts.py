'''
Print out DataONE Coordinating Node hosts.

e.g.

hosts.py -e stage

cn-stage-ucsb-1.test.dataone.org,cn-stage-orc-1.test.dataone.org,cn-stage-unm-1.test.dataone.org


hosts.py -e stage -f json

["cn-stage-ucsb-1.test.dataone.org", "cn-stage-orc-1.test.dataone.org", "cn-stage-unm-1.test.dataone.org"]

'''

import sys
import logging
import argparse
import d1_admin_tools.d1_config
import json


def main():
  parser = argparse.ArgumentParser(description='List envrionment host.')
  parser.add_argument('-l', '--log_level',
                      action='count',
                      default=0,
                      help='Set logging level, multiples for more detailed.')
  parser.add_argument('-e', '--environment',
                      default=None,
                      nargs='?',
                      help="Name of environment to examine or 'list' to list names")
  parser.add_argument('-p', '--primary',
                      default=False,
                      action='store_true',
                      help="List only the primary host(s)")
  parser.add_argument('-f', '--format',
                      default='csv',
                      help='Format for output (csv or json)')
  parser.add_argument('-c', '--config',
                      default=d1_admin_tools.d1_config.CONFIG_FILE,
                      help='Name of configuration file (default = {0}'.format(d1_admin_tools.d1_config.CONFIG_FILE))
  args = parser.parse_args()
  # Setup logging verbosity
  levels = [logging.WARNING, logging.INFO, logging.DEBUG]
  level = levels[min(len(levels) - 1, args.log_level)]
  logging.basicConfig(level=level,
                      format="%(asctime)s %(levelname)s %(message)s")
  config = d1_admin_tools.d1_config.D1Configuration()
  config.load(config_file=args.config)
  environments = []
  if args.environment is None:
    environments = config.environments()
  elif args.environment.lower() == 'list':
    environments = config.environments()
    environments.sort()
    if args.format == "csv":
      print ",".join(environments)
      sys.exit(0)
    if args.format == 'json':
      print json.dumps(environments, indent=2, encoding='utf-8')
      sys.exit(0)
    print "\n".join(environments)
    sys.exit(0)
  else:
    environments = [ args.environment, ]
  hosts = []
  for environment in environments:
    if args.primary:
      hosts.append(config.envPrimaryHost(environment))
    else:
      hosts += config.hosts(environment)
  if args.format.lower() == 'csv':
    print ",".join(hosts)
    return
  if args.format.lower() == 'json':
    print json.dumps(hosts, encoding='utf-8')
    return
  logging.error('Unrecognized format: "%s"', args.format)


if __name__ == "__main__":
  main()
