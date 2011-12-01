#!/usr/bin/python -tt
# vim: ai ts=4 sts=4 et sw=4
#
# Copyright (c) 2011 Intel, Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; version 2 of the License
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc., 59
# Temple Place - Suite 330, Boston, MA 02111-1307, USA.

try:
    import json
except ImportError:
    import simplejson as json

import runner
import msger
from conf import configmgr

SRCSERVER = configmgr.get('src_server')
USER = configmgr.get('user')
PASSWD = configmgr.get('passwd')

def _call_curl(api, *opts, **fields):
    msger.debug('submit data to server %s as user %s' %(SRCSERVER, USER))
    cmdln = "curl -s -u%s:%s " % (USER, PASSWD)
    if opts:
        cmdln += ' '.join(opts)

    for k, v in fields.iteritems():
        cmdln += ' -F%s=%s ' % (k, v)

    cmdln += '%s/%s' % (SRCSERVER, api.lstrip('/'))

    return runner.outs(cmdln)

def build_lastid():
    return _call_curl('job/build/lastBuild/buildNumber')

def build_trigger(params, tarfp):
    _call_curl('job/build/build',
               '-i', 
               name=tarfp,
               file0='@'+tarfp,
               Submit='Build',
               json="%s" % json.dumps(params))

def build_result(id):
    return  _call_curl('job/build/%s/api/json' % id)

def build_mylastresult():
    lastid = build_lastid()
    # In case the last commit is not made by the user, supposed the last
    # job triggered by '$user' is the one. 
    retstr = ''
    while True:
        # TODO, need to enhance
        retstr = build_result(lastid)
        if json.loads(retstr)['userName'] == USER:
            break
        lastid = str(int(lastid) -1)

    # alread find the real id, start to wait for build finished
    while True:
        retstr = build_result(lastid)
        if re.search('building.*false', retstr):
            break

    return json.loads(retstr)

