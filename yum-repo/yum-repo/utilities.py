#!/usr/bin/python
#
# This file is part of the JavaScript Lightweight Widget framework
#
# Copyright (C) 2010-2012, Ian Firns        <firnsy@securixlive.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
# published by the Free Software Foundation.  You may not use, modify or
# distribute this program under any other version of the GNU General
# Public License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#

#
# GLBOAL IMPORTS
import os
import urllib2
from xml.dom.minidom import parse, Node

#
# REPO UTILITY FUNCTIONS

#
# XML UTILITY FUNCTIONS
def xmlToDict(xmlfile):
  doc = parse(xmlfile)

  return elementToDict(doc.documentElement)


def elementToDict(parent):
  child = parent.firstChild

  if (not child):
    return None

  # ignore whitespace and line feed crap
  while child.nodeType == Node.TEXT_NODE and not child.data.strip():
    child = child.nextSibling

  if (child.nodeType == Node.TEXT_NODE):
    return child.nodeValue

  d = {}

  while child is not None:
    if (child.nodeType == Node.ELEMENT_NODE):
      try:
        d[child.tagName]
      except KeyError:
        d[child.tagName] = []

      d[child.tagName].append(elementToDict(child))

    child = child.nextSibling

  return d


#
# URL UTILTIES FUNCTIONS

def downloadFile(src_url, dst_url, overwrite=False):

  if dst_url is None or \
     dst_url == '':
    dst_url = src_url

  if dst_url.startswith("file:///"):
    dst_path = dst_url[7:]
  elif dst_url.startswith("ftp://") or \
       dst_url.startswith("http://"):
    dst_path = tmp_path + "/" + dst_url[dst_url.rindex('/'):]
  else:
    dst_path=dst_url


  if not os.path.exists(dst_path) or overwrite:
    print("DEBUG: Downloading: %s -> %s" % (src_url, dst_path))

    try:
      u = urllib2.urlopen(src_url)
      url_local_handle = open(dst_path, 'w')
      url_local_handle.write(u.read())
      url_local_handle.close()
    except urllib2.URLError, e:
      print e.reason.strerror
      return ''
    except urllib2.HTTPError, e:
      print e.args
      return ''

  return dst_path

