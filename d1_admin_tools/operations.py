'''


'''

import os
import logging
import time

def escapeSolrQueryTerm(term):
  '''
  + - && || ! ( ) { } [ ] ^ " ~ * ? : \
  '''
  reserved = ['+', '-', '&', '|', '!', '(', ')', '{', '}',
              '[', ']', '^', '"', '~', '*', '?', ':',
              ]
  term = term.replace(u'\\', u'\\\\')
  for c in reserved:
    term = term.replace(c, u"\%s" % c)
  return term


def tmpFileName(tmp_dir="/tmp", prefix="", ext="txt"):
  '''
  Returns a temporary file name with a high likelihood of uniqueness.

  :param tmp_dir: Folder to contain the file
  :param prefix: Prefix for file name
  :param ext: Extension for file name (not including the .)
  :return: File name and path relative to tmp_dir.
  '''
  ts = int(time.time()*100000)
  return os.path.join(tmp_dir, "{0}_{1}.{2}".format(prefix, ts, ext))



def resolve(client, pid):
  ''' Resolve the provided identifier in the specified environment

  :param client: An instance of CoordinatingNodeClient
  :param pid: Identifier to resolve
  :return: Dictionary mimicking an objectLocationList with addition of error entry
  '''
  logger = logging.getLogger('main')
  response = {'status':{},
              'xml': None,
              }
  try:
    obj_locs = client.resolve(pid)
    response['status']['msg'] = 'OK'
    response['status']['code'] = client.status_code
    response['xml'] = client.last_response_body #dom.toprettyxml(indent="  ")
    response['identifier'] = unicode(obj_locs.identifier.value())
    response['objectLocation'] = []
    for loc in obj_locs.objectLocation:
      oloc = {'url': unicode(loc.url),
              'nodeIdentifier': unicode(loc.nodeIdentifier.value()),
              'baseURL': unicode(loc.baseURL),
              'version': map(unicode, loc.version),
              'preference': unicode(loc.preference) }
      response['objectLocation'].append(oloc)
  except Exception as e:
    logger.info(e)
    response['status']['msg'] = e.description
    response['status']['code'] = e.errorCode
  return response