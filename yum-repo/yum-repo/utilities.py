#!/usr/bin/python
#
# This file is part of the Yum Repo tool
#
# Copyright (C) 2012, Ian Firns <firnsy@securixlive.com>
# Copyright (C) 2012, Chris Smart <mail@christophersmart.com>
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
import platform
import re
import sys
import urllib2
from urlparse import urljoin
from xml.dom.minidom import parse, Node, NamedNodeMap



class RepoSack:
  def __init__(self):
    self._repos = []

    self._yum_vars = {
      'basedist': 'fedora',
      'dist': platform.linux_distribution()[0].lower(),
      'arch': os.uname()[4],
      'basearch': 'x86_64',
      'releasever': '15'
    }

  def importFromXML(self, path):
    _xml = parse(path)

    _sources = {}
    _name = "unknown"

    # check for yum repo header node
    _root = _xml.firstChild

    if _root.nodeType != Node.ELEMENT_NODE or \
       _root.tagName != "yumrepo":
      return None

    for _child in _root.childNodes:

      # process the name
      if _child.nodeType == Node.ELEMENT_NODE:
        if _child.tagName == "name":

          if _child.hasAttributes() and \
             self._xmlAttributeFilter(_child.attributes):
#            print "DEBUG: Filtered out on Name."
            return None
          elif _child.firstChild.nodeValue == 'fp':
            print "ERROR: \"fp\" is a reserved word"
            return None

          _name = _child.firstChild.nodeValue

        # process the sources
        elif _child.tagName == "sources":

          # iterate
          for _s in _child.childNodes:
            # ignore non-source element nodes
            if _s.nodeType != Node.ELEMENT_NODE or \
               _s.tagName != "source":
                 continue

            # reset the source definition
            _source = {}

            # we have a valid source element node
            for __s in _s.childNodes:
              if __s.nodeType != Node.ELEMENT_NODE:
                continue

              # we have a valid source element node
              if __s.hasAttributes() and \
                 self._xmlAttributeFilter(__s.attributes):
#                print "DEBUG: Filtered source out inner attribute."
                continue

              if not _source.has_key(__s.tagName):
                _source[__s.tagName] = []

              # add the key/value pair after substitution
              _source[__s.tagName].append( self._xmlVariableSubstitute(__s.firstChild.nodeValue) )

            # we should have enough source information now to validate, assume it's valid and test for invalidity

            # require a single id
            if _source.has_key('id'):
              if len(_source['id']) > 1:
                print "ERROR: Only one unique ID per source should be specified."
                continue

              else:
                _source['id'] = _source['id'][0]

            # require a single type
            if _source.has_key('type'):
              if len(_source['type']) > 1:
                print "ERROR: Only one unique type per source should be specified."
                continue

              else:
                _source['type'] = _source['type'][0]

            # require a single package name
            if _source.has_key('packagename'):
              if len(_source['packagename']) > 1:
                print "ERROR: Only one unique package name per source should be specified."
                continue
              else:
                _source['packagename'] = _source['packagename'][0]

            if _source.has_key('url'):
              if len(_source['url']) > 1:
                print "ERROR: Only one valid URL per source should be specified. Check your filters/overrides."
                continue
              else:
                _source['url'] = _source['url'][0]

            # we must be valid so let's add it to the available
            _sources[ _source['id'] ] = _source

        # process the repos
        elif _child.tagName == "repos":

          # iterate
          for _r in _child.childNodes:
            # skip non-repo element nodes
            if _r.nodeType != Node.ELEMENT_NODE or \
               _r.tagName != "repo":
                 continue

            _repo = { 'group': _name }

            # we have a valid source element node
            for __r in _r.childNodes:

              # skip non-element nodes
              if __r.nodeType != Node.ELEMENT_NODE:
                continue

              # we have a valid source element node
              if __r.hasAttributes() and \
                 self._xmlAttributeFilter(__r.attributes):
#                print "DEBUG: Filtered repo out inner attribute."
                continue

              if not _repo.has_key(__r.tagName):
                _repo[__r.tagName] = []

              # add the key/value pair after substitution
              _repo[__r.tagName].append( self._xmlVariableSubstitute(__r.firstChild.nodeValue) )

            # we should have enough repo information now to validate, assume it's valid and test for invalidity

            # require a sindle ID
            if _repo.has_key('id'):
              if len(_repo['id']) > 1:
                print "ERROR: Only one unique ID per repo should be specified."
                continue

              else:
                _repo['id'] = _repo['id'][0]

            if _repo.has_key('source'):
              if len(_repo['source']) > 1:
                print "ERROR: Only one valid source per repo should be specified. Check your filters/overrides."
                continue

              else:
                _repo['source'] = _sources[ _repo['source'][0] ]

            if _repo.has_key('name'):
              if len(_repo['name']) > 1:
                print "ERROR: Only one valid name per repo should be specified. Additional names can be specified by the alias."
                continue

              else:
                _repo['name'] = _repo['name'][0]

            # we must be valid so let's add it to the available
            self._repos.append( Repo( _repo ) )

      else:
        # skip non Element nodes
        pass

      # process the repos

  def importFromURI(self, uri):
    _repos = []

    _source = Source()
    _source.setURL(uri)

    print "DEBUG: auto detecting: %s" % (uri)

    (_proto, _domain, _path, _base, _extension) = parseURI(uri)
    _basename = _base
    if _extension != "":
      _basename += "." + _extension

    _source.setBasename(_basename)

    # first pass determination at the source type
    if _proto == 'http':
      _source.setType(Source.URL_RAW)
    elif _proto == 'https':
      _source.setType(Source.URL_RAW)
    elif _proto == 'ftp':
      _source.setType(Source.URL_RAW)
    elif _proto == 'file':
      _source.setType(Source.URL_LOCAL)

    # check if it's a fedora people URI
    if _proto == 'fp':
      _source.setType(Source.URL_FEDORA_PEOPLE)
      _source.setInstallType(Source.FILE_REPO)

      _source.setURL("http://repos.fedorapeople.org/repos/%s%s/fedora-%s.repo" % ( _domain, _path, _path[1:]))

    elif _extension == "lst":
      _source.setType(Source.URL_MIRROR)
      _source.setInstallType(Source.FILE_MANUAL)

    elif _extension == "repo":
      _source.setType(Source.URL_RAW)
      _source.setInstallType(Source.FILE_REPO)

    elif _extension == "rpm":
      _source.setType(Source.URL_RAW)
      _source.setInstallType(Source.FILE_RPM)

    elif _extension == "xml":
      _source.setType(Source.URL_MIRROR)
      _source.setInstallType(Source.FILE_MANUAL)

    else:
      _source.setType(Source.URL_BASE)
      _source.setInstallType(Source.FILE_MANUAL)

    # if we are a repo let's download and do our best
    if _source.getInstallType() == Source.FILE_REPO:
      _buffer = readFromURI(_source.getURL())

#      print "REPO: %s" % _buffer

      _names = re.compile(r'\[(.*)\]').findall(_buffer)

      for _name in _names:
        _repo = Repo()
        _repo.setName(_name)
        _repo.setSource(_source)
        _repos.append(_repo)




    # otherwise grab the file and we'll take it further
    else:
      print "UNKONWN: %s" % (_source.getInstallType())
      # are we an RPM file




    return _repos


  def getGroups(self):
    _groups = []

    for _r in self._repos:
      if _r.getGroup() not in _groups:
        _groups.append(_r.getGroup())

    return _groups

  def add(self, repo):
    pass


  def search(self, url):
    _repos = []

    _tokens = url.split(":")
# short form
#    rpmfusion:non-free,non-free-debug
#    rpmfusion:*
#    rpmfusion
#
    if _tokens[0] in self.getGroups():

      if len(_tokens) > 1:
        _filter = _tokens[1].split(',')
      else:
        _filter = '*'

      _found = False
      _repos_staging = []

      for _r in self._repos:
        if _r.isGroup(_tokens[0]):
          for _f in _filter:
            if _r.isAlias(_f) or _f == '*':
              _found = True
              _r.enable()

          _repos_staging.append(_r)

      if _found:
        _repos += _repos_staging
      else:
        print "WARNING: Filters did not match any repos."

# fedora-people
#
    elif _tokens[0] == "fp":
      pass

# URL
#    file://
#    http://
#    ftp://

    elif "://" in url:
      (_group, _filter) = url.split("://")

      for _r in self._repos:
        if _r.getSource().isURL(url):
          print "Found a match: %s" % (_r)
          _repos.append(_r)

    elif ":" in url:
      (_group, _filter) = url.split(":")
      _filter = _filter.split(",")

      for _r in self._repos:
        if _r.isGroup(_group):
          for _f in _filter:
            if _r.isAlias(_f):
              print "Found a match: %s" % (_r)
              _repos.append(_r)
              break

    # otherwise assume we are referencing the repo name itself
    else:
      for _r in self._repos:
        if _r.isAlias(url):
          _r.enable()
          _repos.append(_r)

    # satisfy all requires


    # determine conflicts


    return _repos


  def validate(self, url):

    # returns a list of Repo object or objects based on the url provided

    # lookup internally first before manually building
    _repos = self.search(url)

    if len(_repos) == 0:
      # we need to build our repo object manually
      _repos = self.importFromURI(url)

    return _repos


  def _xmlVariableSubstitute(self, _val):
    for _k in self._yum_vars.keys():
      _val = re.sub("\$" + _k, self._yum_vars[_k], _val)

    return _val

  def _xmlAttributeFilter(self, _map):

    # _map is a NamedNodeMap
    if not isinstance(_map, NamedNodeMap):
      return False

    for _i in range(_map.length):
      _n = _map.item(_i).name
      _v = _map.item(_i).value.split(",")

      if _n in self._yum_vars.keys() and \
         self._yum_vars[_n] not in _v:
#        print "DEBUG: Filtering out on %s: %s not in [%s]" % (_n, self._yum_vars[_n], _map.item(_i).value)
        return True

    return False


class Source:
  # source types
  URL_LOCAL         = 0
  URL_RAW           = 1
  URL_BASE          = 2
  URL_MIRROR        = 3
  URL_FEDORA_PEOPLE = 4

  # install types
  FILE_REPO   = 0
  FILE_RPM    = 1
  FILE_MANUAL = 2

  def __init__(self, _object={}):
    self._name = ""
    self._type = Source.URL_RAW
    self._gpg = ""
    self._url = ""

    self._install_type = Source.FILE_MANUAL

    # RPM/REPO specific
    self._basename = ""

    # RPM specific
    self._package_name = ""

    self.loadObject(_object)

  def loadObject(self, _object):
    if _object.has_key('gpg'):
      self._gpg = _object['gpg']

    if _object.has_key('packagename'):
      self._package_name = _object['packagename']

    if _object.has_key('url'):
      self._url = _object['url']

    if _object.has_key('type'):
      if _object['type'] == 'rpm':
        self._install_type = Source.FILE_RPM
      elif _object['type'] == 'repo':
        self._install_type = Source.FILE_RPM
      elif _object['type'] == 'manual':
        self._install_type = Source.FILE_MANUAL

  def getPackageName(self):
    return self._package_name

  def getBasename(self):
    return self._basename

  def setBasename(self, _basename):
    self._basename = _basename

  def getURL(self):
    return self._url

  def setURL(self, _url):
    self._url = _url

  def getType(self):
    return self._type

  def setType(self, _type):
    self._type = _type

  def getGPG(self):
    return self.__gpg

  def setGPG(self, _gpg):
    self._gpg = _gpg

  def getInstallType(self):
    return self._install_type

  def setInstallType(self, install_type):
    self._install_type = install_type

  def isURL(self, url):
    return ( url == self._url )

  def isEqual(self, _source):
    return isinstance(_source, Source) and \
           _source._type == self._type and \
           _source._install_type == self._install_type and \
           _source._url == self._url and \
           _source._gpg == self._gpg

  def __repr__(self):
    self.__str__()

  def __str__(self):
    _str =   "  source: {\n"
    _str +=  "    type: %s\n" % (self._install_type)
    _str +=  "    url: %s\n" % (self._url)

    if self._gpg != "":
      _str +=  "    gpg: %s\n" % (self._gpg)

    if self._package_name != "":
      _str +=  "    package: %s\n" % (self._package_name)

    _str +=  "  }"

    return _str




class Repo:
  # source types
  URL_LOCAL         = 0
  URL_RAW           = 1
  URL_BASE          = 2
  URL_MIRROR        = 3
  URL_FEDORA_PEOPLE = 4

  # install types
  FILE_REPO   = 0
  FILE_RPM    = 1
  FILE_MANUAL = 2

  def __init__(self, _object={}):
    self._source = Source()

    self._group = ""
    self._name = ""
    self._repo_name = ""
    self._alias = []
    self._arch = []
    self._distributions = []

    self._requires = []
    self._conflicts = []

    self._enabled = False

    self.loadObject(_object)

  def getSource(self):
    return self._source

  def setSource(self, _source):
    if isinstance(_source, Source):
      self._source = _source
    else:
      print "ERROR: Expected a Source object."

  def enable(self):
    self._enabled = True

  def disable(self):
    self._enabled = False

  def isEnabled(self):
    return self._enabled

  def getGroup(self):
    return self._group

  def setGroup(self, group):
    self._group = group

  def getName(self):
    return self._name

  def setName(self, name):
    self._name = name

    # set reponame if approriate
    if self._repo_name == "":
      self._repo_name = name

  def getRepoName(self):
    return self._repo_name

  def setRepoName(self, name):
    self._repo_name = name

    # set canonical name if approriate
    if self._name == "":
      self._name = name

  def getArch(self):
    return self._arch

  def addArch(self, arch):
    if not isinstance(arch, list):
      _arch = [ arch ]

    self._arch = list(set(self._arch).union(set(arch)))

  def removeArch(self, arch):
    if not isinstance(arch, list):
      _arch = [ arch ]

    self._arch = list(set(self._arch) - set(arch))

  def addAlias(self, alias):
    if not isinstance(alias, list):
      _alias = [ alias ]

    self._alias = list(set(self._alias).union(set(alias)))

  def removeAlias(self, alias):
    if not isinstance(arch, list):
      _arch = [ arch ]

    self._arch = list(set(self._arch) - set(arch))

  def addRequire(self, _require):
    if not isinstance(_require, list):
      _require = [ _require ]

    self._requires = list(set(self._requires).union(set(_require)))

  def removeRequire(self, _require):
    if not isinstance(_require, list):
      _require = [ _require ]

    self._requires = list(set(self._requires) - set(_require))

  def addConflict(self, _conflict):
    if not isinstance(_conflict, list):
      _conflict = [ _conflict ]

    self._conflicts = list(set(self._conflicts).union(set(_conflict)))

  def removeConflict(self, _conflict):
    if not isinstance(_conflict, list):
      _conflict = [ _conflict ]

    self._conflicts = list(set(self._conflicts) - set(_conflict))


  def loadObject(self, _object):
    if not isinstance(_object, dict):
      return

    if _object.has_key('source'):
      self._source.loadObject(_object['source'])

    if _object.has_key('name'):
      self.setName(_object['name'])

    if _object.has_key('reponame'):
      self.setRepoName(_object['reponame'])

    if _object.has_key('group'):
      self.setGroup(_object['group'])

    if _object.has_key('alias'):
      self.addAlias(_object['alias'])

    if _object.has_key('arch'):
      self.addArch(_object['arch'])

    if _object.has_key('requires'):
      self.addRequire(_object['requires'])

    if _object.has_key('conflicts'):
      self.addConflict(_object['conflicts'])


  def loadBaseUrl(self, url):
    pass


  def isAlias(self, name):
    return ( name in self._alias ) or \
           ( name == self._name ) or \
           ( name == self._repo_name )

  def isGroup(self, group):
    return ( group == self._group )


  def __repr__(self):
    self.__str__()

  def __str__(self):
    _str =   "repo: {\n"
    _str +=  "  name: %s\n" % (self._name)
    _str +=  "  enabled: %s\n" % (self._enabled)

    if len(self._alias) > 0:
      _str +=  "  alias: %s\n" % (self._alias)

    if len(self._conflicts) > 0:
      _str +=  "  conflicts: %s\n" % (self._conflicts)

    if len(self._requires) > 0:
      _str +=  "  requires: %s\n" % (self._requires)

    _str += str(self._source) + "\n"
    _str +=  "}"

    return _str

#
# URL UTILTIES FUNCTIONS

def parseURI(uri):
  _proto = ''
  _domain = ''
  _path = ''
  _base = ''
  _extension = ''

  if "://" in uri:
    (_proto, _path) = uri.split("://")
  elif ":" in uri:
    (_proto, _path) = uri.split(":")
  else:
    _path = uri

  _domain = _path[:_path.find("/")]
  _path = _path[len(_domain):]
  _base = _path[_path.rfind('/')+1:]

  if "." in _path:
    _extension = _base[_base.rfind('.')+1:]
    _base  = _base[:-(len(_extension) + 1)]

  return (_proto, _domain, _path, _base, _extension)


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



def readFromURI(url):

  print "FETCHING: %s" % (url)
  # first pass determination at the source type
  _remote = ( url.startswith('http://') or \
              url.startswith('ftp://') or \
              url.startswith('https://') )

  _buffer = ""


  if _remote:
    try:
      _u = urllib2.urlopen(url)
      _buffer = _u.read()
    except urllib2.URLError, e:
      print e
    except urllib2.HTTPError, e:
      print e

  else:
    try:
      _f = open(url, 'r')
      _buffer = _f.read()
    except:
      print "LOCAL FILE ERROR"

  return _buffer
