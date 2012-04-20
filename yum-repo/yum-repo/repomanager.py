#!/usr/bin/python
#
# This file is part of the JavaScript Lightweight Widget framework
#
# Copyright (C) 2010-2012, Ian Firns        <firnsy@securixlive.com>
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
# GLOBAL IMPORTS
import glob
import rpm
import yum
import urllib2
import urlparse
import os
import pprint

#
# LOCAL IMPORTS
from utilities import xmlToRepoObject, xmlToDict, elementToDict, downloadFile


class RepoManager:

  TMP_PATH       = "/tmp"
  YUM_REPO_PATH  = "/etc/yum/yum-repo.d"
  YUM_REPOS_PATH = "/etc/yum.repos.d"

  # source types
  URL_LOCAL = 0
  URL_RAW = 1
  URL_BASE = 2
  URL_FEDORA_PEOPLE = 3

  # install types
  FILE_REPO = 0
  FILE_RPM  = 1

  def __init__(self):
    self._cache = []
    self._yb = yum.YumBase()
    self._tmp_path = RepoManager.TMP_PATH
    self._yum_repo_path = RepoManager.YUM_REPO_PATH
    self._yum_repos_path = RepoManager.YUM_REPOS_PATH


  def setup(self):
    self.load_repo_cache(self._yum_repo_path)


  def load_repo_cache(self, path):

    cache_files = glob.glob(os.path.join(path, "*.xml"))

    for f in cache_files:
      print "Loading cache file: %s" % f
      self._cache.append( xmlToRepoObject(f) )

#      pp = pprint.PrettyPrinter(indent=2)
#      pp.pprint( xmlToRepoObject( f ) )



  def add_repo(self, repo):

    r = self.format_repo(repo)

    # check for fedora people repo
    if r['source_type'] == RepoManager.URL_FEDORA_PEOPLE:
      return self.add_repo_fedora_people(r['basename'])

    # check short form cache
    if r['cache']:
      return self.add_repo_cache(repo)

    # check for RPM files
    if r['install_type'] == RepoManager.FILE_RPM:
      return self.add_repo_rpm(repo)

    # check if it's a URL
    if r['source_type'] == RepoManager.URL_RAW:
      return self.add_repo_url(repo)

    return 0


  def format_repo(self, repo):

    _repo = {'path': repo, 'basename': repo, 'source_type': 'UNKNOWN', 'install_type': 'UNKNOWN', 'cache': 0, 'filter': ['*']}

    # first pass determination at the source type
    if repo.startswith('http://'):
      _repo['basename'] = repo[7:]
      _repo['source_type'] = RepoManager.URL_RAW
    elif repo.startswith('ftp://'):
      _repo['basename'] = repo[6:]
      _repo['source_type'] = RepoManager.URL_RAW
    elif repo.startswith('https://'):
      _repo['basename'] = repo[8:]
      _repo['source_type'] = RepoManager.URL_RAW

    elif repo.startswith('fp://'):
      _repo['basename'] = repo[5:]
      _repo['install_type'] = RepoManger.URL_FEDORA_PEOPLE
    elif repo.startswith('fp:'):
      _repo['basename'] = repo[3:]
      _repo['source_type'] = RepoManager.URL_FEDORA_PEOPLE

    elif repo.startswith('file:///'):
      _repo['basename'] = repo[8:]
      _repo['install_type'] = RepoManager.URL_LOCAL
    elif repo.startswith('/'):
      _repo['basename'] = repo[1:]
      _repo['install_type'] = RepoManager.URL_LOCAL

    # short form
    elif ':' in repo:
      _repo['basename'] = repo[:repo.index(':')]
      _repo['filter'] = repo[repo.index(':')+1:].split(',')

    print("DEBUG: Calculated basename is %s" % (_repo['basename']))

    # check if it's cached
    for c in self._cache:
      print c['name'][0]
      if c['name'][0] == _repo['basename']:
        print("REPO is cached")
        _repo['cache'] = 1
        break

    if repo.endswith('.rpm'):
      _repo['basename'] = repo[:repo.index(':')]
      _repo['install_type'] = RepoManager.FILE_RPM

    return _repo


#
# ADD METHODS

  def add_repo_cache(self, repo, c):

    # default to all repo branches defined in the cache
    repo_filter = ['*']

    if ':' in repo:
      repo_name = repo[:repo.index(':')]
      repo_filter = repo[repo.index(':')+1:].split(',')

    else:
      repo_name = repo

    # process
    repo_filter_enable = []
    repo_filter_disable = []

    repo_source = []

    # map the requested filter to enable and disable lists
    for r in c['repos'][0]['repo']:

      aliases = set([])
      if r.has_key('alias'):
        aliases = set(r['alias'])

      if r['name'][0] in repo_filter or \
         len(set(repo_filter).intersection(aliases)) or \
         '*' in repo_filter:
        repo_filter_enable.append(r['name'][0])

        # add the source requirement if not accounted for
        if r['source'][0] not in repo_source:
          repo_source.append(r['source'][0])

      else:
        repo_filter_disable.append(r['name'][0])


    # install the sources
    if len(repo_source) == 0:
      return 1

    for s in c['sources'][0]['source']:
      if s['id'][0] in repo_source:
        if s['install_type'][0] == 'rpm':
          self.install_repo_rpm(s['url'][0], s['packagename'][0])

        elif s['install_type'][0] == 'file':
          self.install_repo_file(s['url'][0])

        else:
          print("Unknown source type: %s" % s['install_type'][0])

    # re-read repo configuration
#  yb.getReposFromConfig()

    # enable the repos
    for r in repo_filter_enable:
      r = self._yb.repos.getRepo(r)

      if r.isEnabled():
        continue

      print "Enabling: %s" % r
      r.enablePersistent()


    # disable the repos
    for r in repo_filter_disable:
      r = self._yb.repos.getRepo(r)

      if not r.isEnabled():
        continue

      print "Disabling: %s" % r
      r.disablePersistent()


  def add_repo_fedora_people(self, repo):

    print "Adding fedora people repository: %s" % repo

    repo_tokens = repo.split('/')

    if len(repo_tokens) > 2:
      print "ERROR: Invalid repository specified."
      return 0

    repo_user = repo_tokens[0]
    repo_name = repo_tokens[1]
    repo_url = "http://repos.fedorapeople.org/repos/%s/%s/fedora-%s.repo" % ( repo_user, repo_name, repo_name)

    print "Fetching: %s" % repo_url

    self.install_repo_file(repo_url)

  def add_repo_rpm(self, repo):
    pass


  def add_repo_file(self, repo):
    pass

  def add_repo_url(self, repo):
    pass


#
# INSTALL METHODS


  def install_repo_rpm(self, url, package):
    print("Installing repo, via RPM, from: %s" % url)

    ts = rpm.TransactionSet()

    # trim the file name from the URL
    rpm_file = url[url.rindex('/')+1:]

    mi = ts.dbMatch('name', package)

    if ( mi ):

      if len(mi) > 1:
        print("Ambiguous package name: %s" % package)
      else:
        print("INSTALLED: %s" % package)

    else:
      print("Package NOT installed: %s" % package)

      return

      dst_path = downloadFile(url)

      if not os.path.exists(dst_path):
        print "Error downloading file."
        return 1

      # fetch the file and store locally if required
      fd = os.open(dst_path, os.O_RDONLY)

      ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)

      try:
        h = ts.hdrFromFdno(fd)
      except rpm.error, e:
        print(e)

      os.close(fd)

      ts.addInstall(h, rpm_file, 'i')
      ts.check()
      ts.order()
      ts.run(install_repo_rpm_callback, '')


  def install_repo_rpm_callback(self, reason, amount, total, key, client_data):
      if reason == rpm.RPMCALLBACK_INST_START:
        pass #print "Starting installation."
      elif reason == rpm.RPMCALLBACK_TRANS_STOP:
        pass #print "Transation stopping"



  def install_repo_file(self, url):
    print("Installing repo file from: %s" % url)

    dst_path = os.path.join(self._yum_repos_path, url[url.rindex('/')+1:])

    dst_path = downloadFile(url, dst_path)

    if not os.path.exists(dst_path):
      print "Error downloading file."
      return 1

    # install into the yum repo store


#
# ENABLE/DISABLE METHODS


  def enable_repo(self, repo):
    r = self.format_repo(repo)

    repo_found = False

    # check repoman short form cache
    if r['cache']:
      repo_found = True
      self.enable_repo_cache(repo, c)

    # check for package explicitly
    for r['basename'] in self._yb.repos.findRepos(repo):
      print r
      repo_found = True

      if r.isEnabled():
        continue

      r.enablePersistent()

    if not repo_found:
      print "Repository does not exist."


  def enable_repo_cache(self, repo, c):
    # default to all repo branches defined in the cache
    repo_filter = ['*']

    if ':' in repo:
      repo_name = repo[:repo.index(':')]
      repo_filter = repo[repo.index(':')+1:].split(',')

    else:
      repo_name = repo

    # process
    repo_filter_enable = []

    # map the requested filter to enable and disable lists
    for r in c['repos'][0]['repo']:

      aliases = set([])
      if r.has_key('alias'):
        aliases = set(r['alias'])

      if r['name'][0] in repo_filter or \
         len(set(repo_filter).intersection(aliases)) or \
         '*' in repo_filter:
        repo_filter_enable.append(r['name'][0])

    # enable the repos
    for r in repo_filter_enable:
      r = self._yb.repos.getRepo(r)

      if r.isEnabled():
        continue

      print "Enabling: %s" % r
      r.enablePersistent()


  def disable_repo(self, repo):
    r = self.format_repo(repo)

    repo_found = False

    # check repoman short form cache
    if r['cached']:
      repo_found = True
      disable_repo_cache(repo, c)

    # check for package explicitly
    for r in self._yb.repos.findRepos(repo):
      print r
      repo_found = True

      if not r.isEnabled():
        continue

      r.disablePersistent()

    if not repo_found:
      print "Repository does not exist."


  def disable_repo_cache(self, repo, c):
    # default to all repo branches defined in the cache
    repo_filter = ['*']

    if ':' in repo:
      repo_name = repo[:repo.index(':')]
      repo_filter = repo[repo.index(':')+1:].split(',')

    else:
      repo_name = repo

    # process
    repo_filter_disable = []

    # map the requested filter to enable and disable lists
    for r in c['repos'][0]['repo']:

      aliases = set([])
      if r.has_key('alias'):
        aliases = set(r['alias'])

      if r['name'][0] in repo_filter or \
         len(set(repo_filter).intersection(aliases)) or \
         '*' in repo_filter:
        repo_filter_disable.append(r['name'][0])

    # enable the repos
    for r in repo_filter_disable:
      r = self._yb.repos.getRepo(r)

      if not r.isEnabled():
        continue

      print "Disabling: %s" % r
      r.disablePersistent()


#
# DELETE METHODS
  def delete_repo(self, repo):

    # print warning
    print("WARNING: Disabling or deleting a repository may leave your system without important updates.")

    # check for package explicitly
    r = self.format_repo(repo)

    repo_found = False

    for r in self._yb.repos.findRepos(repo):
      repo_found = True

      if not repo_found:
        continue

      # get the yum repo conf for the repo
      repo_file = r.repofile

      # get repo config if provided by rpm
      package_name = self._yb.pkgSack.searchProvides(repo_file)[0].name
      installed = self._yb.isPackageInstalled(package_name)

      if installed:
        package = self._yb.rpmdb.returnNewestByName(package_name)[0]
        # identify other repo files in rpm
        extra_repos = []
        for r in package.filelist:
          if r.endswith(".repo"):
            extra_repos.append(r)

        # check for other repos in files
        # to do

        # create transaction
        self._yb.remove(package)
        self._yb.buildTransaction()

        # get list of dependencies to also be removed
        deps = []
        for d in self._yb.tsInfo.getMembers():
          if d.name != package_name:
            deps.append(d.name)

        # prompt for deletion and dependencies
        print("\nWARNING: The %s repository is provided by the %s package." % (repo, package_name))
        print("Removing %s will also remove the following repositories:\n" % (package_name))
        for r in extra_repos:
          print("\t%s" % (r))
        print("\n Removing %s will also remove the following dependencies:\n" % (package_name))
        for d in deps:
          print("\t%s" % (d))

        confirm_removal = raw_input("\nRemove %s? (y/N): " % (package_name))
        if confirm_removal.upper().startswith("Y"):
          #remove the rpm
          print("Removing RPM that provides %s repository" % (repo))
          self._yb.processTransaction()
        else:
          # reverse transaction
          self._yb.tsInfo.pkgdict = {}
      else:
        # need to delete the file manually because it's not provided by an rpm
        os.remove(repo_file)

    if not repo_found:
      print "Repository does not exist."

#
# LIST METHODS
  def list_repos_enabled(self):
    repos = {}

    for r in self._yb.repos.listEnabled():
      repo_name = str(r)
      repos[repo_name] = r

    rs = repos.keys()
    rs.sort()

    if len(rs):
      max_repo_title_length = len( max(rs, key=len) ) + 2
      format_str = "%-" + str(max_repo_title_length) + "s %-10s"

      print(format_str % ("Repository", "Cost"))
      print(format_str % ("----------", "----"))
      for r in rs:
        print(format_str % (r, repos[r].cost))
    else:
      print "No repos are currently enabled."


  def list_repos_all(self):
    repos = {}

    for r in self._yb.repos.findRepos('*'):
      repo_name = str(r)
      repos[repo_name] = r

    rs = repos.keys()
    rs.sort()

    max_repo_title_length = len( max(rs, key=len) ) + 2
    format_str = "%-" + str(max_repo_title_length) + "s %-10s %-10s"

    print(format_str % ("Repository", "Enabled", "Cost"))
    print(format_str % ("----------", "-------", "----"))

    for r in rs:
      found = "y" if repos[r].isEnabled() else "n"
      print(format_str % (r, found, repos[r].cost))

