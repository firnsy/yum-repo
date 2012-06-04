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
from utilities import xmlToRepoObject, elementToDict, downloadFile, RepoSack, Repo, Source


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
    self._reposack = RepoSack()
    self._cache = []
    self._yb = yum.YumBase()
    self._tmp_path = RepoManager.TMP_PATH
    self._yum_repo_path = RepoManager.YUM_REPO_PATH
    self._yum_repos_path = RepoManager.YUM_REPOS_PATH


  def setup(self):
    self.load_repo_cache(self._yum_repo_path)


  def load_repo_cache(self, path):

    cache_files = glob.glob(os.path.join(path, "*.xml"))

    _loaded = []

    for f in cache_files:
      try:
        self._reposack.importFromXML(f)

      except:
        print "  - %s (Error)" % f

      else:
        _loaded.append(os.path.basename(f))

    if len(_loaded) > 0:
      print "Loaded repo definitions: %s" % ( ", ".join(_loaded) )


  def add_repo(self, repo):

    _repos = self._reposack.validate(repo)
    _sources = []

    # consolidate unique sources
    for _r in _repos:
      for _s in _sources:
        if _s.isEqual(_r.getSource()):
          break;

      else:
        _sources.append(_r.getSource())

    # install the sources
    for _s in _sources:
      if _s.getInstallType() == Source.FILE_REPO:
        self.install_repo(_s)

      elif _s.getInstallType() == Source.FILE_RPM:
        self.install_rpm(_s)

      elif _s.getInstallType() == Source.FILE_MANUAL:
        self.install_manual(_s)

    # enable/disable the repos
    for _r in _repos:
      _yr = self._yb.repos.getRepo(_r.getName())

      if _yr.isEnabled() != _r.isEnabled():
        if _r.isEnabled():
          _yr.enablePersistent()

        else:
          _yr.disablePersistent()

    return 0



#
# INSTALL METHODS

  def install_rpm(self, _source):
    ts = rpm.TransactionSet()

    mi = ts.dbMatch('name', _source.getPackageName())

    if ( mi ):
      if len(mi) > 1:
        print("Ambiguous package name: %s" % _source.getPackageName())

      else:
        print("INSTALLED: %s" % _source.getPackageName())

    else:
      print("Installing repo, via RPM, from: %s" % _source.getURL())

      return

      dst_path = downloadFile(_source.getURL())

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

      ts.addInstall(h, _source.getBasename(), 'i')
      ts.check()
      ts.order()
      ts.run(install_rpm_callback, '')


  def install_rpm_callback(self, reason, amount, total, key, client_data):
    if reason == rpm.RPMCALLBACK_INST_START:
      pass #print "Starting installation."

    elif reason == rpm.RPMCALLBACK_TRANS_STOP:
      pass #print "Transation stopping"


  def install_repo(self, _source):
    print("Installing repo file from: %s" % _source.getURL())

    dst_path = os.path.join(self._yum_repos_path, _source.getBasename())

    dst_path = downloadFile(url, dst_path)

    if not os.path.exists(dst_path):
      print "Error downloading file."
      return 1

  def install_manual(self, _source):
    pass

#
# ENABLE/DISABLE METHODS

  def enable_repo(self, repo):
    _repos = self._reposack.validate(repo)

    # enable/disable the repos
    for _r in _repos:
      _yr = self._yb.repos.getRepo(_r.getName())

      if _yr.isEnabled() != _r.isEnabled():
        _yr.enablePersistent()


  def disable_repo(self, repo):
    _repos = self._reposack.validate(repo)

    # enable/disable the repos
    for _r in _repos:
      _yr = self._yb.repos.getRepo(_r.getName())

      if _yr.isEnabled() == _r.isEnabled():
        _yr.disablePersistent()


#
# DELETE METHODS
  def delete_repo(self, repo):

    # print warning
    print("WARNING: Disabling or deleting a repository may leave your system without important updates.")

    _repos = self._reposack.validate(repo)
    _sources = []

    # consolidate unique sources
    for _r in _repos:
      for _s in _sources:
        if _s.isEqual(_r.getSource()):
          break;

      else:
        _sources.append(_r.getSource())

    repo_found = False

    for _r in _repos:
      if not _r.isEnabled():
        continue

      _yr = self._yb.repos.findRepos(_r.getRepoName())

      if _yr is None:
        continue
      elif len(_yr) > 1:
        print "WARNING: Multiple repos by the name of: %s" % (_r.getRepoName())

      repo_found = True

      # get the yum repo conf for the repo
      repo_file = _yr[0].repofile

      # check if repo is provided by rpm
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

        if len(deps) > 0:
          print("\nRemoving %s will also remove the following dependencies:\n" % (package_name))
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

