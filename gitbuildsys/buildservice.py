#
# buildservice.py - Buildservice API support for Yabsc
#

# Copyright (C) 2008 James Oakley <jfunk@opensuse.org>
# Copyright (C) 2010, 2011, 2012 Intel, Inc.

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

import os
import shutil
import tempfile
import time
import urlparse
import urllib2
import xml.etree.cElementTree as ElementTree
from osc import conf, core

class ObsError(Exception):
    pass

# Injection code for osc.core to fix the empty XML bug
def solid_get_files_meta(self, revision='latest', skip_service=True):
    from time import sleep
    import msger
    try:
        from xml.etree import cElementTree as ET
    except ImportError:
        import cElementTree as ET

    retry_count = 3
    while retry_count > 0:
        fm = core.show_files_meta(self.apiurl, self.prjname, self.name,
                                  revision=revision, meta=self.meta)
        try:
            root = ET.fromstring(fm)
            break
        except SyntaxError, err:
            msger.warning('corrupted or empty obs server response ,retrying ...')
            sleep(1)
            retry_count -= 1

    if not retry_count:
        # all the re-try failed, abort
        raise ObsError('cannet fetch files meta xml from server')

    # look for "too large" files according to size limit and mark them
    for e in root.findall('entry'):
        size = e.get('size')
        if size and self.size_limit and int(size) > self.size_limit \
            or skip_service and (e.get('name').startswith('_service:') or e.get('name').startswith('_service_')):
            e.set('skipped', 'true')
    return ET.tostring(root)

core.Package.get_files_meta = solid_get_files_meta

class _Metafile:
    """
    _Metafile(url, input, change_is_required=False, file_ext='.xml')

    Implementation on osc.core.metafile that does not print to stdout
    """

    def __init__(self, url, input, change_is_required=False, file_ext='.xml'):
        self.url = url
        self.change_is_required = change_is_required

        (fd, self.filename) = tempfile.mkstemp(prefix = 'osc_metafile.', suffix = file_ext, dir = '/tmp')

        f = os.fdopen(fd, 'w')
        f.write(''.join(input))
        f.close()

        self.hash_orig = core.dgst(self.filename)

    def sync(self):
        hash = core.dgst(self.filename)
        if self.change_is_required == True and hash == self.hash_orig:
            os.unlink(self.filename)
            return True

        # don't do any exception handling... it's up to the caller what to do in case
        # of an exception
        core.http_PUT(self.url, file=self.filename)
        os.unlink(self.filename)
        return True

# helper functions for class _ProjectFlags
def _flag2bool(flag):
    """
    _flag2bool(flag) -> Boolean
    Returns a boolean corresponding to the string 'enable', or 'disable'
    """

    if flag == 'enable':
        return True
    elif flag == 'disable':
        return False

def _bool2flag(b):
    """
    _bool2flag(b) -> String

    Returns 'enable', or 'disable' according to boolean value b
    """
    if b == True:
        return 'enable'
    elif b == False:
        return 'disable'

class _ProjectFlags(object):
    """
    _ProjectFlags(bs, project)

    Represents the flags in project through the BuildService object bs
    """

    def __init__(self, bs, project):
        self.bs = bs
        self.tree = ElementTree.fromstring(self.bs.getProjectMeta(project))

        # The "default" flags, when undefined
        self.defaultflags = {'build': True,
                             'publish': True,
                             'useforbuild': True,
                             'debuginfo': False}

        # Figure out what arches and repositories are defined
        self.arches = {}
        self.repositories = {}

        # Build individual repository list
        for repository in self.tree.findall('repository'):
            repodict = {'arches': {}}
            self.__init_flags_in_dict(repodict)
            for arch in repository.findall('arch'):
                repodict['arches'][arch.text] = {}
                self.__init_flags_in_dict(repodict['arches'][arch.text])
                # Add placeholder in global arches
                self.arches[arch.text] = {}
            self.repositories[repository.get('name')] = repodict

        # Initialise flags in global arches
        for archdict in self.arches.values():
            self.__init_flags_in_dict(archdict)

        # A special repository representing the global and global arch flags
        self.allrepositories = {'arches': self.arches}
        self.__init_flags_in_dict(self.allrepositories)

        # Now populate the structures from the xml data
        for flagtype in ('build', 'publish', 'useforbuild', 'debuginfo'):
            flagnode = self.tree.find(flagtype)
            if flagnode:
                for node in flagnode:
                    repository = node.get('repository')
                    arch = node.get('arch')

                    if repository and arch:
                        self.repositories[repository]['arches'][arch][flagtype] = _flag2bool(node.tag)
                    elif repository:
                        self.repositories[repository][flagtype] = _flag2bool(node.tag)
                    elif arch:
                        self.arches[flagtype] = _flag2bool(node.tag)
                    else:
                        self.allrepositories[flagtype] = _flag2bool(node.tag)

    def __init_flags_in_dict(self, d):
        """
        __init_flags_in_dict(d)

        Initialize all build flags to None in d
        """
        d.update({'build': None,
                  'publish': None,
                  'useforbuild': None,
                  'debuginfo': None})

    def save(self):
        """
        save()

        Save flags
        """

        for flagtype in ('build', 'publish', 'useforbuild', 'debuginfo'):
            # Clear if set
            flagnode = self.tree.find(flagtype)
            if flagnode:
                self.tree.remove(flagnode)

            # Generate rule nodes
            rulenodes = []

            # globals
            if self.allrepositories[flagtype] != None:
                rulenodes.append(ElementTree.Element(_bool2flag(self.allrepositories[flagtype])))
            for arch in self.arches:
                if self.arches[arch][flagtype] != None:
                    rulenodes.append(ElementTree.Element(_bool2flag(self.arches[arch][flagtype]), arch=arch))

            # repositories
            for repository in self.repositories:
                if self.repositories[repository][flagtype] != None:
                    rulenodes.append(ElementTree.Element(_bool2flag(self.repositories[repository][flagtype]), repository=repository))
                for arch in self.repositories[repository]['arches']:
                    if self.repositories[repository]['arches'][arch][flagtype] != None:
                        rulenodes.append(ElementTree.Element(_bool2flag(self.repositories[repository]['arches'][arch][flagtype]), arch=arch, repository=repository))

            # Add nodes to tree
            if rulenodes:
                from pprint import pprint
                pprint(rulenodes)
                flagnode = ElementTree.Element(flagtype)
                self.tree.insert(3, flagnode)
                for rulenode in rulenodes:
                    flagnode.append(rulenode)

        print ElementTree.tostring(self.tree)

class BuildService(object):
    """Interface to Build Service API"""

    def __init__(self, apiurl=None, oscrc=None):
        if oscrc:
            try:
                conf.get_config(override_conffile = oscrc)
            except OSError, e:
                if e.errno == 1:
                    # permission problem, should be the chmod(0600) issue
                    raise RuntimeError, 'Current user has no write permission for specified oscrc: %s' % oscrc

                raise # else
        else:
            conf.get_config()

        if apiurl:
            self.apiurl = apiurl
        else:
            self.apiurl = conf.config['apiurl']

    def getAPIServerList(self):
        """getAPIServerList() -> list

        Get list of API servers configured in .oscrc
        """
        apiservers = []
        for host in conf.config['api_host_options'].keys():
            apiurl = "%s://%s" % (conf.config['scheme'], host)
        return apiservers

    # the following two alias api are added temporarily for compatible safe
    def is_new_package(self, dst_project, dst_package):
        return self.isNewPackage(dst_project, dst_package)
    def gen_req_info(self, reqid, show_detail = True):
        return self.genRequestInfo(reqid, show_detail)

    def isNewPackage(self, dst_project, dst_package):
        """Check whether the dst pac is a new one
        """

        new_pkg = False
        try:
            core.meta_exists(metatype = 'pkg',
                        path_args = (core.quote_plus(dst_project), core.quote_plus(dst_package)),
                        create_new = False,
                        apiurl = self.apiurl)
        except urllib2.HTTPError, e:
            if e.code == 404:
                new_pkg = True
            else:
                raise e
        return new_pkg

    def isNewProject(self, project):
        """Check whether the specified prject is a new one
        """

        new_prj = False
        try:
            core.meta_exists(metatype = 'prj',
                        path_args = (core.quote_plus(project)),
                        create_new = False,
                        apiurl = self.apiurl)
        except urllib2.HTTPError, e:
            if e.code == 404:
                new_prj = True
            else:
                raise e

        return new_prj

    def genRequestInfo(self, reqid, show_detail = True):
        """Generate formated diff info for request,
        mainly used by notification mails from BOSS
        """

        def _gen_request_diff():
            """ Recommanded getter: request_diff can get req diff info even if req is accepted/declined
            """
            reqdiff = ''

            try:
                diff = core.request_diff(self.apiurl, reqid)

                try:
                    reqdiff += diff.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        reqdiff += diff.decode('iso-8859-1')
                    except UnicodeDecodeError:
                        pass

            except (AttributeError, urllib2.HTTPError), e:
                return None

            return reqdiff

        def _gen_server_diff(req):
            """ Reserved getter: get req diff, if and only if the recommanded getter failed 
            """
            reqdiff = ''

            src_project = req.actions[0].src_project
            src_package = req.actions[0].src_package
            src_rev = req.actions[0].src_rev
            try:
                dst_project = req.actions[0].dst_project
                dst_package = req.actions[0].dst_package
            except AttributeError:
                dst_project = req.actions[0].tgt_project
                dst_package = req.actions[0].tgt_package

            # Check whether the dst pac is a new one
            new_pkg = False
            try:
                core.meta_exists(metatype = 'pkg',
                            path_args = (core.quote_plus(dst_project), core.quote_plus(dst_package)),
                            create_new = False,
                            apiurl = self.apiurl)
            except urllib2.HTTPError, e:
                if e.code == 404:
                    new_pkg = True
                else:
                    raise e

            if new_pkg:
                src_fl = self.getSrcFileList(src_project, src_package, src_rev)

                spec_file = None
                yaml_file = None
                for f in src_fl:
                    if f.endswith(".spec"):
                        spec_file = f
                    elif f.endswith(".yaml"):
                       yaml_file = f

                reqdiff += 'This is a NEW package in %s project.\n' % dst_project

                reqdiff += 'The files in the new package:\n'
                reqdiff += '%s/\n' % src_package
                reqdiff += '  |__  ' + '\n  |__  '.join(src_fl)

                if yaml_file:
                    reqdiff += '\n\nThe content of the YAML file, %s:\n' % (yaml_file)
                    reqdiff += '===================================================================\n'
                    reqdiff += self.getSrcFileContent(src_project, src_package, yaml_file, src_rev)
                    reqdiff += '\n===================================================================\n'

                if spec_file:
                    reqdiff += '\n\nThe content of the spec file, %s:\n' % (spec_file)
                    reqdiff += '===================================================================\n'
                    reqdiff += self.getSrcFileContent(src_project, src_package, spec_file, src_rev)
                    reqdiff += '\n===================================================================\n'
                else:
                    reqdiff += '\n\nspec file NOT FOUND!\n'

            else:
                try:
                    diff = core.server_diff(self.apiurl,
                                        dst_project, dst_package, None,
                                        src_project, src_package, src_rev, False)

                    try:
                        reqdiff += diff.decode('utf-8')
                    except UnicodeDecodeError:
                        try:
                            reqdiff += diff.decode('iso-8859-1')
                        except UnicodeDecodeError:
                            pass

                except urllib2.HTTPError, e:
                    e.osc_msg = 'Diff not possible'
                    return ''

            return reqdiff

        ####################################
        # function implementation start here

        req = core.get_request(self.apiurl, reqid)
        try:
            req.reviews = []
            reqinfo = unicode(req)
        except UnicodeEncodeError:
            reqinfo = u''

        if show_detail:
            diff = _gen_request_diff()
            if diff is None:
                diff = _gen_server_diff(req)

            reqinfo += diff

        # the result, in unicode string
        return reqinfo

    def reqAccept(self, reqid, msg=''):
        """ This method is called to accept a request
            Success: return None
            Failed:  return string of error message
        """

        try:
            core.change_request_state(self.apiurl, reqid, 'accepted', message=msg, supersed=None)
        except Exception, e:
            return str(e)

        return None

    def reqDecline(self, reqid, msg=''):
        """ This method is called to decline a request
            Success: return None
            Failed:  return string of error message
        """

        try:
            core.change_request_state(self.apiurl, reqid, 'declined', message=msg, supersed=None)
        except Exception, e:
            return str(e)

        return None

    def reqRevoke(self, reqid, msg=''):
        """ This method is called to revoke a request
            Success: return None
            Failed:  return string of error message
        """

        try:
            core.change_request_state(self.apiurl, reqid, 'revoked', message=msg, supersed=None)
        except Exception, e:
            return str(e)

        return None

    def reqReview(self, reqid, user='', group='', msg=''):
        """ This method is called to add review msg to a request
            Success: return None
            Failed:  return string of error message
        """
        try:
            query = { 'cmd': 'addreview' }
            if user:
                query['by_user'] = user
            if group:
                query['by_group'] = group
            u = core.makeurl(self.apiurl, ['request', reqid], query=query)
            f = core.http_POST(u, data=msg)
            root = ElementTree.parse(f).getroot()
            root.get('code')
        except Exception, e:
            return str(e)

        return None

    def getSrcFileList(self, project, package, revision=None):
        """ get source file list of prj/pac
        """

        return core.meta_get_filelist(self.apiurl, project, package, expand=True, revision=revision)

    def getSrcFileContent(self, project, package, path, revision=None):
        """ Cat remote file
        """

        rev = core.show_upstream_xsrcmd5(self.apiurl, project, package, revision=revision)
        if rev:
            query = { 'rev': rev }
        else:
            query = None

        u = core.makeurl(self.apiurl, ['source', project, package, core.pathname2url(path)], query=query)

        content = ''
        for buf in core.streamfile(u, core.http_GET, core.BUFSIZE):
            content += buf

        # return unicode str
        return content.decode('utf8')

    def getSrcFileChecksum(self, project, package, path, revision=None):
        """ getSrcFileChecksum(project, package, path, revision=None) -> string
            returns source md5 of a source file
        """

        query = {}
        query['expand'] = 1
        if revision:
            query['rev'] = revision

        u = core.makeurl(self.apiurl, ['source', project, package], query=query)
        f = core.http_GET(u)
        root = ElementTree.parse(f).getroot()

        for node in root.findall('entry'):
            if node.get('name') == path:
                return node.get('md5')

        return None

    def getPackageChecksum(self, project, package, revision=None):
        """ getPackageChecksum(project, package, revision=None) -> string
            returns srcmd5 of a package
        """

        query = {}
        query['expand'] = 1
        if revision:
            query['rev'] = revision

        u = core.makeurl(self.apiurl, ['source', project, package], query=query)
        f = core.http_GET(u)
        root = ElementTree.parse(f).getroot()

        return root.get('srcmd5')

    def getLinkinfo(self, project, package, revision=None):
        """ getLinkinfo(project, package, revision=None) -> (linked_prj, linked_pkg, linked_srcmd5)
            returns link info of a prj/pkg
        """

        query = {}
        query['expand'] = 1
        if revision:
            query['rev'] = revision

        u = core.makeurl(self.apiurl, ['source', project, package], query=query)
        f = core.http_GET(u)
        root = ElementTree.parse(f).getroot()

        for node in root.findall('linkinfo'):
            return (node.get('project'), node.get('package'), node.get('srcmd5'))

        return None

    def getUserData(self, user, *tags):
        """getUserData() -> str

        Get the user data
        """
        return core.get_user_data(self.apiurl, user, *tags)

    def getUserName(self):
        """getUserName() -> str

        Get the user name associated with the current API server
        """
        return conf.config['api_host_options'][self.apiurl]['user']

    def getProjectList(self):
        """getProjectList() -> list

        Get list of projects
        """
        return [project for project in core.meta_get_project_list(self.apiurl) if project != 'deleted']

    def getWatchedProjectList(self):
        """getWatchedProjectList() -> list

        Get list of watched projects
        """
        username = self.getUserName()
        tree = ElementTree.fromstring(''.join(core.get_user_meta(self.apiurl, username)))
        projects = []
        watchlist = tree.find('watchlist')
        if watchlist:
            for project in watchlist.findall('project'):
                projects.append(project.get('name'))
        homeproject = 'home:%s' % username
        if not homeproject in projects and homeproject in self.getProjectList():
            projects.append(homeproject)
        return projects

    def watchProject(self, project):
        """
        watchProject(project)

        Watch project
        """
        username = self.getUserName()
        data = core.meta_exists('user', username, create_new=False, apiurl=self.apiurl)
        url = core.make_meta_url('user', username, self.apiurl)

        person = ElementTree.fromstring(''.join(data))
        watchlist = person.find('watchlist')
        if not watchlist:
            watchlist = ElementTree.SubElement(person, 'watchlist')
        ElementTree.SubElement(watchlist, 'project', name=str(project))

        f = _Metafile(url, ElementTree.tostring(person))
        f.sync()

    def unwatchProject(self, project):
        """
        watchProject(project)

        Watch project
        """
        username = self.getUserName()
        data = core.meta_exists('user', username, create_new=False, apiurl=self.apiurl)
        url = core.make_meta_url('user', username, self.apiurl)

        person = ElementTree.fromstring(''.join(data))
        watchlist = person.find('watchlist')
        for node in watchlist:
            if node.get('name') == str(project):
                watchlist.remove(node)
                break

        f = _Metafile(url, ElementTree.tostring(person))
        f.sync()

    def getRepoState(self, project):
        targets = {}
        tree = ElementTree.fromstring(''.join(core.show_prj_results_meta(self.apiurl, project)))
        for result in tree.findall('result'):
            targets[('/'.join((result.get('repository'), result.get('arch'))))] = result.get('state')
        return targets

    def getResults(self, project):
        """getResults(project) -> (dict, list)

        Get results of a project. Returns (results, targets)

        results is a dict, with package names as the keys, and lists of result codes as the values

        targets is a list of targets, corresponding to the result code lists
        """
        results = {}
        targets = []
        tree = ElementTree.fromstring(''.join(core.show_prj_results_meta(self.apiurl, project)))
        for result in tree.findall('result'):
            targets.append('/'.join((result.get('repository'), result.get('arch'))))
            for status in result.findall('status'):
                package = status.get('package')
                code = status.get('code')
                if not package in results:
                    results[package] = []
                results[package].append(code)
        return (results, targets)

    def getDiff(self, sprj, spkg, dprj, dpkg, rev):
        diff = ''
        diff += core.server_diff(self.apiurl, sprj, spkg, None,
                 dprj, dpkg, rev, False, True)
        return diff

    def getTargets(self, project):
        """
        getTargets(project) -> list

        Get a list of targets for a project
        """
        targets = []
        tree = ElementTree.fromstring(''.join(core.show_project_meta(self.apiurl, project)))
        for repo in tree.findall('repository'):
            for arch in repo.findall('arch'):
                targets.append('%s/%s' % (repo.get('name'), arch.text))
        return targets

    def getPackageStatus(self, project, package):
        """
        getPackageStatus(project, package) -> dict

        Returns the status of a package as a dict with targets as the keys and status codes as the
        values
        """
        status = {}
        tree = ElementTree.fromstring(''.join(core.show_results_meta(self.apiurl, project, package)))
        for result in tree.findall('result'):
            target = '/'.join((result.get('repository'), result.get('arch')))
            statusnode = result.find('status')
            code = statusnode.get('code')
            details = statusnode.find('details')
            if details is not None:
                code += ': ' + details.text
            status[target] = code
        return status

    def getProjectDiff(self, src_project, dst_project):
        diffs = []

        packages = self.getPackageList(src_project)
        for src_package in packages:
            diff = core.server_diff(self.apiurl,
                                dst_project, src_package, None,
                                src_project, src_package, None, False)
            diffs.append(diff)

        return '\n'.join(diffs)

    def getPackageList(self, prj, deleted=None):
        query = {}
        if deleted:
           query['deleted'] = 1

        u = core.makeurl(self.apiurl, ['source', prj], query)
        f = core.http_GET(u)
        root = ElementTree.parse(f).getroot()
        return [ node.get('name') for node in root.findall('entry') ]

    def getBinaryList(self, project, target, package):
        """
        getBinaryList(project, target, package) -> list

        Returns a list of binaries for a particular target and package
        """

        (repo, arch) = target.split('/')
        return core.get_binarylist(self.apiurl, project, repo, arch, package)

    def getBinary(self, project, target, package, file, path):
        """
        getBinary(project, target, file, path)

        Get binary 'file' for 'project' and 'target' and save it as 'path'
        """

        (repo, arch) = target.split('/')
        core.get_binary_file(self.apiurl, project, repo, arch, file, target_filename=path, package=package)

    def getBuildLog(self, project, target, package, offset=0):
        """
        getBuildLog(project, target, package, offset=0) -> str

        Returns the build log of a package for a particular target.

        If offset is greater than 0, return only text after that offset. This allows live streaming
        """

        (repo, arch) = target.split('/')
        u = core.makeurl(self.apiurl, ['build', project, repo, arch, package, '_log?nostream=1&start=%s' % offset])
        return core.http_GET(u).read()

    def getWorkerStatus(self):
        """
        getWorkerStatus() -> list of dicts

        Get worker status as a list of dictionaries. Each dictionary contains the keys 'id',
        'hostarch', and 'status'. If the worker is building, the dict will additionally contain the
        keys 'project', 'package', 'target', and 'starttime'
        """

        url = core.makeurl(self.apiurl, ['build', '_workerstatus'])
        f = core.http_GET(url)
        tree = ElementTree.parse(f).getroot()
        workerstatus = []
        for worker in tree.findall('building'):
            d = {'id': worker.get('workerid'),
                 'status': 'building'}
            for attr in ('hostarch', 'project', 'package', 'starttime'):
                d[attr] = worker.get(attr)
            d['target'] = '/'.join((worker.get('repository'), worker.get('arch')))
            d['started'] = time.asctime(time.localtime(float(worker.get('starttime'))))
            workerstatus.append(d)
        for worker in tree.findall('idle'):
            d = {'id': worker.get('workerid'),
                 'hostarch': worker.get('hostarch'),
                 'status': 'idle'}
            workerstatus.append(d)
        return workerstatus

    def getWaitStats(self):
        """
        getWaitStats() -> list

        Returns the number of jobs in the wait queue as a list of (arch, count)
        pairs
        """

        url = core.makeurl(self.apiurl, ['build', '_workerstatus'])
        f = core.http_GET(url)
        tree = ElementTree.parse(f).getroot()
        stats = []
        for worker in tree.findall('waiting'):
            stats.append((worker.get('arch'), int(worker.get('jobs'))))
        return stats

    def getSubmitRequests(self):
        """
        getSubmitRequests() -> list of dicts

        """

        url = core.makeurl(self.apiurl, ['search', 'request', '?match=submit'])
        f = core.http_GET(url)
        tree = ElementTree.parse(f).getroot()
        submitrequests = []
        for sr in tree.findall('request'):
            if sr.get('type') != "submit":
                continue

            d = {'id': int(sr.get('id'))}
            sb = sr.findall('submit')[0]
            src = sb.findall('source')[0]
            d['srcproject'] = src.get('project')
            d['srcpackage'] = src.get('package')
            dst = sb.findall('target')[0]
            d['dstproject'] = dst.get('project')
            d['dstpackage'] = dst.get('package')
            d['state'] = sr.findall('state')[0].get('name')

            submitrequests.append(d)
        submitrequests.sort(key=lambda x: x['id'])
        return submitrequests

    def rebuild(self, project, package, target=None, code=None):
        """
        rebuild(project, package, target, code=None)

        Rebuild 'package' in 'project' for 'target'. If 'code' is specified,
        all targets with that code will be rebuilt
        """

        if target:
            (repo, arch) = target.split('/')
        else:
            repo = None
            arch = None
        return core.rebuild(self.apiurl, project, package, repo, arch, code)

    def abortBuild(self, project, package=None, target=None):
        """
        abort(project, package=None, target=None)

        Abort build of a package or all packages in a project
        """

        if target:
            (repo, arch) = target.split('/')
        else:
            repo = None
            arch = None
        return core.abortbuild(self.apiurl, project, package, arch, repo)

    def getBuildHistory(self, project, package, target):
        """
        getBuildHistory(project, package, target) -> list

        Get build history of package for target as a list of tuples of the form
        (time, srcmd5, rev, versrel, bcnt)
        """

        (repo, arch) = target.split('/')
        u = core.makeurl(self.apiurl, ['build', project, repo, arch, package, '_history'])
        f = core.http_GET(u)
        root = ElementTree.parse(f).getroot()

        r = []
        for node in root.findall('entry'):
            rev = int(node.get('rev'))
            srcmd5 = node.get('srcmd5')
            versrel = node.get('versrel')
            bcnt = int(node.get('bcnt'))
            t = time.localtime(int(node.get('time')))
            t = time.strftime('%Y-%m-%d %H:%M:%S', t)

            r.append((t, srcmd5, rev, versrel, bcnt))
        return r

    def getCommitLog(self, project, package, revision=None):
        """
        getCommitLog(project, package, revision=None) -> list

        Get commit log for package in project. If revision is set, get just the
        log for that revision.

        Each log is a tuple of the form (rev, srcmd5, version, time, user,
        comment)
        """

        u = core.makeurl(self.apiurl, ['source', project, package, '_history'])
        f = core.http_GET(u)
        root = ElementTree.parse(f).getroot()

        r = []
        revisions = root.findall('revision')
        revisions.reverse()
        for node in revisions:
            rev = int(node.get('rev'))
            if revision and rev != int(revision):
                continue
            srcmd5 = node.find('srcmd5').text
            version = node.find('version').text
            user = node.find('user').text
            try:
                comment = node.find('comment').text
            except:
                comment = '<no message>'
            t = time.localtime(int(node.find('time').text))
            t = time.strftime('%Y-%m-%d %H:%M:%S', t)

            r.append((rev, srcmd5, version, t, user, comment))
        return r

    def getProjectMeta(self, project):
        """
        getProjectMeta(project) -> string

        Get XML metadata for project
        """

        return ''.join(core.show_project_meta(self.apiurl, project))

    def getProjectData(self, project, tag):
        """
        getProjectData(project, tag) -> list
        
        Return a string list if node has text, else return the values dict list
        """

        data = []
        tree = ElementTree.fromstring(self.getProjectMeta(project))
        nodes = tree.findall(tag)
        if nodes:
            for node in nodes:
                node_value = {}
                for key in node.keys():
                    node_value[key] = node.get(key)

                if node_value:
                    data.append(node_value)
                else:
                    data.append(node.text)

        return data

    def getProjectPersons(self, project, role):
        """
        getProjectPersons(project, role) -> list
        
        Return a userid list in this project with this role
        """

        userids = []
        persons = self.getProjectData(project, 'person')
        for person in persons:
            if person.has_key('role') and person['role'] == role:
                userids.append(person['userid'])

        return userids

    def getProjectDevel(self, project):
        """
        getProjectDevel(project) -> tuple (devel_prj, devel_pkg)

        Return the devel tuple of a project if it has the node, else return None
        """

        devels = self.getProjectData(project, 'devel')
        for devel in devels:
            if devel.has_key('project') and devel.has_key('package'):
                return (devel['project'], devel['package'])

        return None

    def getProjectLink(self, project):
        """
        getProjectLink(project) -> string

        Return the linked project of a project if it has the node, else return None
        """

        links = self.getProjectData(project, 'link')
        for link in links:
            if link.has_key('project'):
                return link['project']

        return None

    def deleteProject(self, project):
        """
        deleteProject(project)
        
        Delete the specific project
        """

        try:
            core.delete_project(self.apiurl, project)
        except Exception:
            return False
            
        return True

    def getPackageMeta(self, project, package):
        """
        getPackageMeta(project, package) -> string

        Get XML metadata for package in project
        """

        return ''.join(core.show_package_meta(self.apiurl, project, package))

    def getPackageData(self, project, package, tag):
        """
        getPackageData(project, package, tag) -> list
        
        Return a string list if node has text, else return the values dict list
        """

        data = []
        tree = ElementTree.fromstring(self.getPackageMeta(project, package))
        nodes = tree.findall(tag)
        if nodes:
            for node in nodes:
                node_value = {}
                for key in node.keys():
                    node_value[key] = node.get(key)

                if node_value:
                    data.append(node_value)
                else:
                    data.append(node.text)

        return data

    def getPackagePersons(self, project, package, role):
        """
        getPackagePersons(project, package, role) -> list
        
        Return a userid list in the package with this role
        """

        userids = []
        persons = self.getPackageData(project, package, 'person')
        for person in persons:
            if person.has_key('role') and person['role'] == role:
                userids.append(person['userid'])

        return userids

    def getPackageDevel(self, project, package):
        """
        getPackageDevel(project, package) -> tuple (devel_prj, devel_pkg)
        
        Return the devel tuple of a package if it has the node, else return None
        """

        devels = self.getPackageData(project, package, 'devel')
        for devel in devels:
            if devel.has_key('project') and devel.has_key('package'):
                return (devel['project'], devel['package'])

        return None

    def deletePackage(self, project, package):
        """
        deletePackage(project, package)
        
        Delete the specific package in project
        """

        try:
            core.delete_package(self.apiurl, project, package)
        except Exception:
            return False
            
        return True

    def projectFlags(self, project):
        """
        projectFlags(project) -> _ProjectFlags

        Return a _ProjectFlags object for manipulating the flags of project
        """

        return _ProjectFlags(self, project)

    def checkout(self, prj, pkg, rev='latest'):
        """ checkout the package to current dir with link expanded
        """

        core.checkout_package(self.apiurl, prj, pkg, rev, prj_dir=prj, expand_link=True)

    def findPac(self, wd='.'):
        """Get the single Package object for specified dir
          the 'wd' should be a working dir for one single pac
        """

        if core.is_package_dir(wd):
            return core.findpacs([wd])[0]
        else:
            return None

    def mkPac(self, prj, pkg):
        """Create empty package for new one under CWD
        """

        core.make_dir(self.apiurl, prj, pkg, pathname = '.')

        pkg_path = os.path.join(prj, pkg)
        shutil.rmtree(pkg_path, ignore_errors = True)
        os.chdir(prj)
        core.createPackageDir(pkg)

    def submit(self, msg, wd='.'):
        if not core.is_package_dir(wd):
            # TODO show some error message
            return

        pac = core.findpacs([wd])[0]
        prj = os.path.normpath(os.path.join(pac.dir, os.pardir))
        pac_path = os.path.basename(os.path.normpath(pac.absdir))
        files = {}
        files[pac_path] = pac.todo
        core.Project(prj).commit(tuple([pac_path]), msg=msg, files=files)
        core.store_unlink_file(pac.absdir, '_commit_msg')

    def branchPkg(self, src_project, src_package, rev=None, target_project=None, target_package=None):
        """Create branch package from `src_project/src_package`
          arguments:
            rev: revision of src project/package
            target_project: name of target proj, use default one if None
            target_package: name of target pkg, use the same as asrc if None
        """

        if target_project is None:
            target_project = 'home:%s:branches:%s' \
                             % (conf.get_apiurl_usr(self.apiurl), src_project)

        if target_package is None:
            target_package = src_package

        exists, targetprj, targetpkg, srcprj, srcpkg = \
            core.branch_pkg(self.apiurl,
                            src_project,
                            src_package,
                            rev=rev,
                            target_project=target_project,
                            target_package=target_package,
                            force=True)

        return (targetprj, targetpkg)

    def get_buildconfig(self, prj, repository):
        return core.get_buildconfig(self.apiurl, prj, repository)

    def get_repos(self, prj):
        repos = []
        for repo in core.get_repos_of_project(self.apiurl, prj):
            repos.append(repo)
        return repos

    def get_ArchitectureList(self, prj, target):
        """
        return the list of Archictecture of the target of the projectObsName for a OBS server.
        """
        url = core.makeurl(self.apiurl,['build', prj, target])
        f = core.http_GET(url)
        if f == None:
            return None

        aElement = ElementTree.fromstring(''.join(f.readlines()))
        result = []
        for directory in aElement:
            for entry in directory.getiterator():
                result.append(entry.get("name"))

        return result

