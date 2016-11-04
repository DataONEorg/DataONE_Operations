"""
Implements a generic wrapper around a DataONE response type for format translation


"""

import json
from xml.etree.ElementTree import fromstring
from xmljson import badgerfish as bf
from d1_admin_tools import d1_config

def indentXML(elem, level=0, indent='  '):
  i = "\n" + level * indent
  j = "\n" + (level - 1) * indent
  if len(elem):
    if not elem.text or not elem.text.strip():
      elem.text = i + indent
    if not elem.tail or not elem.tail.strip():
      elem.tail = i
    for subelem in elem:
      indentXML(subelem, level + 1)
    if not elem.tail or not elem.tail.strip():
      elem.tail = j
  else:
    if level and (not elem.tail or not elem.tail.strip()):
      elem.tail = j
  return elem


class DataONEResponse( object ):

  def __init__(self, obj=None, xml=None, indent=2 ):
    self.content = obj
    self.xml = xml
    self.indent = indent
    self.setContent(obj, xml=xml)


  def setContent(self, obj, xml=None):
    self.content = obj
    if xml is None:
      if hasattr( obj, 'toxml' ):
        self.xml = obj.toxml()
      else:
        dom = self.content.toDOM(None)
        self.xml = dom.toprettyxml(indent=self.indent*u' ')
    else:
      self.xml = xml


  def asXML(self):
    return self.xml


  def asJSON(self):
    if self.content is None:
      return None
    jdata = bf.data(fromstring(self.asXML()))
    return json.dumps(jdata, indent=self.indent, encoding=d1_config.ENCODING)


  def __unicode__(self):
    return self.asJSON()


def asJSON(obj):
  if hasattr(obj, 'asJSON'):
     return obj.asJSON()
  return json.dumps(obj, encoding=d1_config.ENCODING, indent=2)


def asXML(obj):
  return obj.asXML()
