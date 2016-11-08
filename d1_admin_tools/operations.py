'''


'''

import logging


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