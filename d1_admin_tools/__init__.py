"""

"""
import sys
import os
import logging
import logging.handlers
import atexit
import datetime
import d1_config
import dateparser
from pytz import timezone


def textToDateTime(txt, default_tz='UTC'):
  logger = logging.getLogger('main')
  d = dateparser.parse(txt, settings={'RETURN_AS_TIMEZONE_AWARE': True})
  if d is None:
    logger.error("Unable to convert '%s' to a date time.", txt)
    return d
  if d.tzinfo is None or d.tzinfo.utcoffset(d) is None:
    logger.warn('No timezone information specified, assuming UTC')
    return d.replace(tzinfo = timezone('UTC'))
  return d


class LogFormatter(logging.Formatter):
  converter = datetime.datetime.fromtimestamp
  def formatTime(self, record, datefmt=None):
    ct = self.converter(record.created)
    if datefmt:
      s = ct.strftime(datefmt)
    else:
      t = ct.strftime("%Y-%m-%d %H:%M:%S")
      s = "%s,%03d" % (t, record.msecs)
    return s


def exitMessage(name):
  logging.info("====== END:%s ======", name)


def setupLogger(name, level=logging.WARN, log_file=None, file_log_level=logging.INFO):
  logger = logging.getLogger('')
  for handler in logger.handlers:
    logger.removeHandler(handler)
  logger.setLevel(logging.DEBUG)
  formatter = LogFormatter(fmt='%(asctime)s %(name)s %(levelname)s: %(message)s',
                           datefmt='%Y%m%dT%H%M%S.%f%z')
  if not log_file is None:
    #Lot to UTC so messages can be more easily compared with logs on the CNs
    l1 = logging.handlers.TimedRotatingFileHandler(filename=log_file,
                                                   when='D',
                                                   interval=1,
                                                   utc=True,
                                                   encoding='utf-8')
    l1.setFormatter(formatter)
    l1.setLevel(file_log_level)
    logger.addHandler(l1)
    logging.info("====== START:%s ======", name)
    atexit.register(exitMessage, name)
  l2 = logging.StreamHandler()
  l2.setFormatter(formatter)
  l2.setLevel(level)
  logger.addHandler(l2)


def defaultScriptMain(parser,
                      arg_defaults=None,
                      with_config=True,
                      with_environment=True,
                      with_format=True):
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
  if with_config:
    parser.add_argument('-c', '--config',
                        default=defaults['config'],
                        help='Name of configuration file (default = {0}'.format(defaults['config']))
  if with_environment:
    parser.add_argument('-e', '--environment',
                        default=defaults['environment'],
                        help="Name of environment to examine (default = production)")
  if with_format:
    parser.add_argument('-f', '--format',
                        default=defaults['format'][0],
                        help='Output format ({0})'.format(",".join(defaults['format'])))
  parser.add_argument('-l', '--log_level',
                      action='count',
                      default=defaults['log_level'],
                      help='Set logging level, multiples for more detailed.')
  command = " ".join(sys.argv)
  args = parser.parse_args()
  if not with_environment:
    args.environment = "production"
  # Setup logging verbosity
  levels = [logging.WARNING, logging.INFO, logging.DEBUG]
  level = levels[min(len(levels) - 1, args.log_level)]
  config = d1_config.D1Configuration()
  config.load()
  app_name = os.path.basename(sys.argv[0])
  log_file = os.path.join(config.getLogFolder(args.environment), app_name) + ".log"
  setupLogger(app_name, level=level, log_file=log_file, file_log_level=logging.INFO)
  logging.info("Logging initialized at level %s", logging.getLevelName(level))
  logging.info(command)
  return args, config

