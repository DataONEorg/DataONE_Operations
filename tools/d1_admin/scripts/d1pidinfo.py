'''
Check for the presences of an identifier on the coordinating nodes for an envronment.

export CN="cn-sandbox-ucsb-1.test.dataone.org"
export HOSTS="cn-sandbox-ucsb-1.test.dataone.org,cn-sandbox-unm-1.test.dataone.org,cn-sandbox-orc-1.test.dataone.org"

fab -I -H${CN} -f d1_pid_presence.py


getPIDdocID:dc9a6703-497a-4891-897f-b6ec08c657802-180_2_Nanno_neg.rdf

autogen.2016081114450596136

d1_pid_presence -E environment -V verbosity PID

'''

import os
import yaml
import argparse
import logging
from fabric.api import hide, run, sudo, put, parallel, get, env, task, hosts, settings
from fabric.contrib import files as fabfiles

ENVIRONMENTS={'production':{'primary':'cn.dataone.org',
                            'cns': ['cn-ucsb-1.dataone.org',
                                    'cn-unm-1.dataone.org',
                                    'cn-orc-1.dataone.org',
                                    ],
                            },
              'stage':{'primary':'cn-stage.test.dataone.org',
                       'cns': ['cn-stage-ucsb-1.test.dataone.org',
                               'cn-stage-orc-1.test.dataone.org',
                               'cn-stage-unm-1.test.dataone.org',
                               ],
                       },
              'stage-2': {'primary':'cn-stage-2.test.dataone.org',
                          'cns': ['cn-stage-unm-2.test.dataone.org',
                                 ],
                          },
              'sandbox': {'primary':'cn-sandbox.test.dataone.org',
                          'cns': ['cn-sandbox-ucsb-1.test.dataone.org',
                                  'cn-sandbox-orc-1.test.dataone.org',
                                  'cn-sandbox-unm-1.test.dataone.org',
                                 ],
                       },
              'sandbox-2':{'primary':'cn-sandbox-2.test.dataone.org',
                           'cns': ['cn-sandbox-ucsb-2.test.dataone.org',
                                  ],
                       },
              'dev':{'primary':'cn-dev.test.dataone.org',
                       'cns': ['cn-dev-ucsb-1.test.dataone.org',
                               'cn-dev-orc-1.test.dataone.org',
                               'cn-dev-unm-1.test.dataone.org',
                               ],
                       },
              'dev-2':{'primary':'cn-dev-2.test.dataone.org',
                       'cns': ['cn-dev-ucsb-2.test.dataone.org',
                               'cn-dev-unm-2.test.dataone.org',
                               ],
                       },
              }



DATADIR = "/var/metacat/data"

accumulator = {'data':{},
               'files':{},
               }


def setEnvironment(environment):
    env.hosts = ENVIRONMENTS[environment]['cns']


def _getPIDdocID(pid, pg_readonly="dataone_readonly"):
    '''
    Lookup the docid for the provided PID
    :param pid: The PID to lookup.
    :param user: User that command should be run as (postgres)
    :return: The docid for the provided PID or None if not present
    '''
    SQL = "SELECT guid, docid, rev FROM identifier WHERE guid IN (SELECT guid"
    SQL += " FROM systemmetadata WHERE "
    SQL += " guid = '" + pid + "');"
    cmd = "psql -h localhost -U {0} metacat --single-transaction --no-align -t --field-separator ' '".format(pg_readonly)
    cmd += " -P pager=off --quiet  -c \"" + SQL + "\""
    res = run( cmd )
    res = res.split(" ")
    response = {'data':{},
                'errors':[],
                }
    try:
        data = {"pid":res[0],
                "autogen": res[1],
                "revision": res[2],
                "docid": "{1}.{2}".format(*res)}
        response['data'] = data
    except IndexError as e:
        response['errors'].append("PID not found in database: \"{0}\"".format(pid))
    return response


def getPIDdocID( pid ):
    res = _getPIDdocID(pid )
    #print "pid:{pid}\ndocid:{docid}".format(**res)
    print yaml.dump(res, explicit_start=True)


def _confirmDocID(docid):
    '''
    Return info about the provided docid on each host requested.
    :param docid:
    :return:
    '''
    res = {'exists': False,
           'size': None,
           'date_modified': None,
           'SHA224': None,
           'head': None,
           }
    path = os.path.join(DATADIR, docid)
    res['exists'] = fabfiles.exists(path)
    if res['exists']:
        fhead = run("head \"{0}\"".format(path))
        res['head'] = str(fhead)
        #size birth access modified change
        fstat = run("stat -c \"%s %W %X %Y %Z\" \"{0}\"".format(path)).split()
        res['size'] = fstat[0]
        res['date_modified'] = fstat[3]
        sha224 = run("sha224sum \"{0}\"".format(path))
        res['SHA224'] = sha224.strip().split(" ")[0]
    return res


def confirmDocID(docid):
    res = _confirmDocID(docid)
    print yaml.dump(res, explicit_start=True)


def checkFiles():
    accumulator['files'][env.host] = _confirmDocID(accumulator['data']['data']['docid'])


def checkPID(pid):
    data =  _getPIDdocID( pid )
    if data is not None:
        accumulator['data'] = data


def report(show_content=False):
    consistent = True
    hosts = accumulator['files'].keys()
    checksum = accumulator['files'][hosts[0]]['SHA224']
    for host in hosts[1:]:
        if checksum != accumulator['files'][host]['SHA224']:
            consistent = False
    print """PID: {pid}
autogen: {autogen}
revision: {revision}
docid: {docid}""".format(**accumulator['data']['data'])
    print "consistent: {0}".format(str(consistent))
    if show_content:
        for host in accumulator['files']:
            print "Host: {0}".format(host)
            print """  exists: {exists}
  size: {size}
  modified: {date_modified}
  sha224: {SHA224}
  head: {head}
  """.format(**accumulator['files'][host])


def main():
  parser = argparse.ArgumentParser(description='Inspect PID in a DataONE environment.')
  parser.add_argument('-l', '--log_level',
                      action='count',
                      default=0,
                      help='Set logging level, multiples for more detailed.')
  parser.add_argument('-e', '--environment',
                      default='dev',
                      help="Name of environment to examine ({0})".format(", ".join(ENVIRONMENTS.keys())))
  parser.add_argument('-p', '--per_node',
                      action="store_true",
                      help="Show per node info for PID")
  parser.add_argument('pid',
                      help="Identifier to evaluate")
  args = parser.parse_args()

  # Setup logging verbosity
  levels = [logging.WARNING, logging.INFO, logging.DEBUG]
  level = levels[min(len(levels) - 1, args.log_level)]
  logging.basicConfig(level=level,
                      format="%(asctime)s %(levelname)s %(message)s")

  environment = args.environment
  pid = args.pid
  #  pid = "dc9a6703-497a-4891-897f-b6ec08c657802-180_2_Nanno_neg.rdf"
  #  verbose=1
  with settings(hide('warnings', 'running', 'stdout', 'stderr'),
                host_string=ENVIRONMENTS[environment]['primary'],
                ):
    logging.info("Getting DocID for {0}".format(pid))
    accumulator['data'] = _getPIDdocID(pid)
  for host in ENVIRONMENTS[environment]['cns']:
    logging.info("Getting content state on {0}".format(host))
    with settings(hide('warnings', 'running', 'stdout', 'stderr'),
                  host_string=host):
      accumulator['files'][host] = _confirmDocID(accumulator['data']['data']['docid'])
  report(show_content=args.per_node)


if __name__ == "__main__":
  main()