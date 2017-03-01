'''
Configuration for DataONE client admin tools
'''

import os
import logging
import codecs
import json
import pprint
import d1_nodes

ENCODING = 'utf-8'
CONFIG_FOLDER = os.path.join( os.getenv("HOME"), ".dataone" )
CONFIG_FILE = os.path.join( CONFIG_FOLDER, "d1_config.json" )
DEFAULT_API_VERSION='2'

#----- D1Configuration -----
class D1Configuration( object ):
  '''Provides access and initialization mechanisms for a configuration file
  for various DataONE utilities.
  '''

  def __init__(self):
    self._L = logging.getLogger( self.__class__.__name__)
    self.config = {}
    self.config_folder = CONFIG_FOLDER


  def environments(self):
    ''' List environment names

    :return: list of environment names
    '''
    return self.config['environments'].keys()


  def environment(self, environment):
    '''
    Return configuration structure for specified environment
    :param environment: name of environment
    :return: environment configuration structure
    '''
    return self.config['environments'][environment]


  def envPrimary(self, environment):
    '''
    Primary host information for specified environment
    :param environment: name of environment
    :return: dictionary of {host: ,base: } for environment
    '''
    return self.config['environments'][environment]['primary']


  def envPrimaryHost(self, environment):
    '''
    Host name of primary host for an environment.
    :param environment: environment name
    :return: hostname
    '''
    return self.config['environments'][environment]['primary']['host']


  def envPrimaryBase(self, environment):
    '''

    :param environment:
    :return:
    '''
    env = self.config['environments'][environment]['primary']
    return env['base']


  def envPrimaryBaseURL(self, environment):
    '''Return the base URL of the primary host for the specified environment.
    :param environment: name of environment
    :return: BaseURL
    '''
    env = self.config['environments'][environment]['primary']
    return "https://{0}{1}".format(env['host'], env['base'])


  def envPrimaryNodeId(self, environment):
    env = self.config['environments'][environment]['primary']
    return env['id']


  def envNodes(self, environment):
    '''
    Return the list of nodes for the specified environment.

    Note that the nodes are not loaded into the node structure until .load() is called.

    :param environment: name of environment
    :return: instance of d1_nodes.Nodes
    '''
    nodes = d1_nodes.Nodes(self.envPrimaryBaseURL(environment))
    return nodes


  def hosts(self, environment):
    '''
    Return a list of host names for the specified environment
    :param environment: name of environment
    :return: List of host names
    '''
    res = []
    for cn in self.config['environments'][environment]['cns']:
      res.append(cn['host'])
    return res


  def getLogFolder(self, environment):
    '''
    Returns an environment specific folder to contain logs.

    Defaults to a folder "log" under the folder from which the config was loaded. By
    default, this is: ${HOME}/.dataone/log

    :param environment:
    :return: file path for the log folder
    '''
    log_folder = os.path.join(self.config_folder, "log")
    if not os.path.exists(log_folder):
      os.makedirs(log_folder)
    return log_folder


  def load(self, config_file=CONFIG_FILE):
    self.config_folder = os.path.dirname(config_file)
    with codecs.open( config_file, 'rb', encoding=ENCODING ) as fp:
      self.config = json.load(fp)


  def save(self, config_file=CONFIG_FILE):
    with codecs.open( config_file, 'wb', encoding=ENCODING ) as fp:
      json.dump( self.config, fp, indent=2 )


  def initialize(self):
    self.config = {}

    #Version of the configuration file structure
    self.config['version'] = '1.1.0'

    #Initialize the various environment settings
    self.config['environments'] = {'production': {'primary': {'host':'cn.dataone.org', 'base':'/cn', 'id': 'urn:node:CN', },
                                                  'cns': [{'host':'cn-ucsb-1.dataone.org','base':'/cn',},
                                                          {'host':'cn-unm-1.dataone.org','base':'/cn',},
                                                          {'host':'cn-orc-1.dataone.org','base':'/cn',},
                                                          ],
                                                  'login':{'cert':'https://cilogon.org/?skin=dataone',
                                                           'token':''},
                                                  'postgres': {'readonly': 'dataone_readonly',
                                                               'pg_hba.conf': '/etc/postgresql/9.3/main/pg_hba.conf'},
                                                  },
                                   'stage': {'primary': {'host':'cn-stage.test.dataone.org', 'base':'/cn', 'id':'urn:node:cnStage', },
                                             'cns': [{'host':'cn-stage-ucsb-1.test.dataone.org', 'base':'/cn',  },
                                                     {'host':'cn-stage-orc-1.test.dataone.org', 'base':'/cn', },
                                                     {'host':'cn-stage-unm-1.test.dataone.org', 'base':'/cn',},
                                                     ],
                                             'login': {'cert': 'https://cilogon.org/?skin=dataonestage',
                                                       'token': ''},
                                             'postgres': {'readonly': 'dataone_readonly',
                                                          'pg_hba.conf': '/etc/postgresql/9.3/main/pg_hba.conf'},
                                             },
                                   'stage-2': {'primary': {'host':'cn-stage-2.test.dataone.org', 'base':'/cn', 'id':'urn:node:cnStage2'},
                                               'cns': [{'host':'cn-stage-unm-2.test.dataone.org', 'base':'/cn', },
                                                       ],
                                               'login': {'cert': 'https://cilogon.org/?skin=dataonestage2',
                                                         'token': ''},
                                               'postgres': {'readonly': 'dataone_readonly',
                                                            'pg_hba.conf': '/etc/postgresql/9.3/main/pg_hba.conf'},
                                               },
                                   'sandbox': {'primary': {'host':'cn-sandbox.test.dataone.org', 'base':'/cn', 'id':'urn:node:cnSandbox', },
                                               'cns': [{'host':'cn-sandbox-ucsb-1.test.dataone.org', 'base':'/cn', },
                                                       {'host':'cn-sandbox-orc-1.test.dataone.org', 'base':'/cn', },
                                                       {'host':'cn-sandbox-unm-1.test.dataone.org', 'base':'/cn', },
                                                       ],
                                               'login': {'cert': 'https://cilogon.org/?skin=dataonesandbox',
                                                         'token': ''},
                                               'postgres': {'readonly': 'dataone_readonly',
                                                            'pg_hba.conf': '/etc/postgresql/9.3/main/pg_hba.conf'},
                                               },
                                   'sandbox-2': {'primary': {'host':'cn-sandbox-2.test.dataone.org', 'base':'/cn',  'id':'urn:node:cnSandbox2',},
                                                 'cns': [{'host':'cn-sandbox-ucsb-2.test.dataone.org', 'base':'/cn', },
                                                         ],
                                                 'login': {'cert': 'https://cilogon.org/?skin=dataonesandbox2',
                                                           'token': ''},
                                                 'postgres': {'readonly': 'dataone_readonly',
                                                              'pg_hba.conf': '/etc/postgresql/9.3/main/pg_hba.conf'},
                                                 },
                                   'dev': {'primary': {'host':'cn-dev.test.dataone.org', 'base':'/cn',  'id':'urn:node:cnDev',},
                                           'cns': [{'host':'cn-dev-ucsb-1.test.dataone.org', 'base':'/cn', },
                                                   {'host':'cn-dev-orc-1.test.dataone.org', 'base':'/cn', },
                                                   {'host':'cn-dev-unm-1.test.dataone.org', 'base':'/cn', },
                                                   ],
                                           'login': {'cert': 'https://cilogon.org/?skin=dataonedev',
                                                     'token': ''},
                                           'postgres': {'readonly': 'dataone_readonly',
                                                        'pg_hba.conf': '/etc/postgresql/9.3/main/pg_hba.conf'},
                                           },
                                   'dev-2': {'primary': {'host':'cn-dev-2.test.dataone.org', 'base':'/cn',  'id':'urn:node:cnDev2',},
                                             'cns': [{'host':'cn-dev-ucsb-2.test.dataone.org', 'base':'/cn', },
                                                     {'host':'cn-dev-unm-2.test.dataone.org', 'base':'/cn', },
                                                     ],
                                             'login': {'cert': 'https://cilogon.org/?skin=dataonedev2',
                                                       'token': ''},
                                             'postgres': {'readonly': 'dataone_readonly',
                                                          'pg_hba.conf': '/etc/postgresql/9.3/main/pg_hba.conf'},
                                             },
                                   }
    # A postgres username that is allowedread only access to the CN database (when logged into CN only
    self.config['posgresql'] =  {"user": "dataone_readonly",
                  "host": "localhost"},
    # Some info needed for poking around the metacat installation
    self.config['metacat'] = {"data": "/var/metacat/data"}

  def dump(self):
    pprint.pprint( self.config, indent=2 )


#----- Main -----
if __name__ == "__main__":
  import sys
  import argparse
  parser = argparse.ArgumentParser(description='Initialize or dump a configuration file for DataONE tools.')
  parser.add_argument('-l', '--log_level',
                      action='count',
                      default=0,
                      help='Set logging level, multiples for more detailed.')
  parser.add_argument('-i', '--initialize',
                      action='store_true',
                      default=False,
                      help='Initialize the configuration file with default values.')
  parser.add_argument('-c', '--config',
                      default=CONFIG_FILE,
                      help='Specify alternate configuration file ({0}).'.format(CONFIG_FILE))
  args = parser.parse_args()
  # Setup logging verbosity
  levels = [logging.WARNING, logging.INFO, logging.DEBUG]
  level = levels[min(len(levels) - 1, args.log_level)]
  logging.basicConfig(level=level,
                      format="%(asctime)s %(levelname)s %(message)s")
  conf = D1Configuration()
  config_file = args.config
  if args.initialize:
    if os.path.exists(config_file):
      logging.error("The configuration file %s already exists. Rename or remove to initialize.", config_file)
      sys.exit(1)
    logging.info("Initializing config file %s", config_file)
    os.makedirs(os.path.basename(config_file))
    conf.initialize()
    conf.save(config_file)
    sys.exit(0)
  logging.info("Loading from %s", config_file)
  conf.load(config_file)
  conf.dump()
