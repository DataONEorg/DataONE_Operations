"""

"""

import logging
import d1_config


def defaultScriptMain(parser, arg_defaults=None):
  '''
  Default Main method for scripts.

  Doesn't do anything except parse argument, setup logging and load config.

  Adds arguments:

  -c --config:      optional path to configuration
  -e --environment: name of environment
  -f --format:      name of output format
  -l --log_level:   flag to turn on logging, more means more detailed logging.

  :param parser: Instance of argparse.ArgumentParser already configured with expected parameters
  :return: (args, config) Parsed argument and an instance of D1Configuration
  '''
  defaults = { 'format': ['text', 'json', 'yaml'],
               'config': d1_config.CONFIG_FILE,
               'environment': 'production',
               'log_level': 0,
             }
  if arg_defaults is None:
    arg_defaults = {}
  defaults.update(arg_defaults)
  parser.add_argument('-c', '--config',
                      default=defaults['config'],
                      help='Name of configuration file (default = {0}'.format(defaults['config']))
  parser.add_argument('-e', '--environment',
                      default=defaults['environment'],
                      help="Name of environment to examine (default = production)")
  parser.add_argument('-f', '--format',
                      default=defaults['format'][0],
                      help='Output format ({0})'.format(",".join(defaults['format'])))
  parser.add_argument('-l', '--log_level',
                      action='count',
                      default=defaults['log_level'],
                      help='Set logging level, multiples for more detailed.')
  args = parser.parse_args()
  # Setup logging verbosity
  levels = [logging.WARNING, logging.INFO, logging.DEBUG]
  level = levels[min(len(levels) - 1, args.log_level)]
  logging.basicConfig(level=level,
                      format="%(asctime)s %(levelname)s %(message)s")
  config = d1_config.D1Configuration()
  config.load()
  return args, config

