# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# DataStax Hyper-Converged Database (HCD) clusters

from __future__ import absolute_import

import os
import re
import subprocess
import shutil
import tarfile
import tempfile
from argparse import ArgumentError
from distutils.version import LooseVersion

from ccmlib import common, repository
from ccmlib.cluster import Cluster
from ccmlib.common import ArgumentError, rmdirs
from ccmlib.hcd.hcd_node import HcdNode

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser


HCD_CASSANDRA_CONF_DIR = "resources/cassandra/conf"
HCD_ARCHIVE = "https://downloads.datastax.com/hcd/hcd-%s-bin.tar.gz"


def isHcd(install_dir, options=None):
    if install_dir is None:
        raise ArgumentError('Undefined installation directory')
    bin_dir = os.path.join(install_dir, common.BIN_DIR)
    if options and options.hcd and './' != install_dir and not os.path.exists(bin_dir):
        raise ArgumentError('Installation directory does not contain a bin directory: %s' % install_dir)
    if options and options.hcd:
        return True
    hcd_script = os.path.join(bin_dir, 'hcd')
    if options and not options.hcd and './' != install_dir and os.path.exists(hcd_script):
        raise ArgumentError('Installation directory is HCD but options did not specify `--hcd`: %s' % install_dir)

    return os.path.exists(hcd_script)

def isHcdClusterType(install_dir, options=None):
    if isHcd(install_dir, options):
        return HcdCluster
    return None


class HcdCluster(Cluster):

    @staticmethod
    def getConfDir(install_dir):
        if isHcd(install_dir):
            return os.path.join(install_dir, HCD_CASSANDRA_CONF_DIR)
        raise RuntimeError("illegal call to HcdCluster.getConfDir() when not HCD")

    @staticmethod
    def getNodeClass():
        return HcdNode


    def __init__(self, path, name, partitioner=None, install_dir=None, create_directory=True, version=None, verbose=False, derived_cassandra_version=None, options=None):
        self._cassandra_version = None
        if derived_cassandra_version:
            self._cassandra_version = derived_cassandra_version

        super(HcdCluster, self).__init__(path, name, partitioner, install_dir, create_directory, version, verbose, options)

    def can_generate_tokens(self):
        return False

    def load_from_repository(self, version, verbose):
        return setup_hcd(version, verbose)

    def create_node(self, name, auto_bootstrap, thrift_interface, storage_interface, jmx_port, remote_debug_port, initial_token, save=True, binary_interface=None, byteman_port='0', environment_variables=None, derived_cassandra_version=None, **kwargs):
        return HcdNode(name, self, auto_bootstrap, thrift_interface, storage_interface, jmx_port, remote_debug_port, initial_token, save, binary_interface, byteman_port, environment_variables=environment_variables, derived_cassandra_version=derived_cassandra_version, **kwargs)

    def cassandra_version(self):
        if self._cassandra_version is None:
            self._cassandra_version = get_hcd_cassandra_version(self.get_install_dir())
        return self._cassandra_version


def download_hcd_version(version, verbose=False):
    url = HCD_ARCHIVE
    if repository.CCM_CONFIG.has_option('repositories', 'hcd'):
        url = repository.CCM_CONFIG.get('repositories', 'hcd')

    url = url % version
    _, target = tempfile.mkstemp(suffix=".tar.gz", prefix="ccm-")
    try:
        repository.__download(url, target, show_progress=verbose)
        common.debug("Extracting {} as version {} ...".format(target, version))
        tar = tarfile.open(target)
        dir = tar.next().name.split("/")[0]  # pylint: disable=all
        tar.extractall(path=repository.__get_dir())
        tar.close()
        target_dir = os.path.join(repository.__get_dir(), version)
        if os.path.exists(target_dir):
            rmdirs(target_dir)
        shutil.move(os.path.join(repository.__get_dir(), dir), target_dir)
    except urllib.error.URLError as e:
        msg = "Invalid version %s" % version if url is None else "Invalid url %s" % url
        msg = msg + " (underlying error is: %s)" % str(e)
        raise ArgumentError(msg)
    except tarfile.ReadError as e:
        raise ArgumentError("Unable to uncompress downloaded file: %s" % str(e))


def setup_hcd(version, verbose=False):
    (cdir, version, fallback) = repository.__setup(version, verbose)
    if cdir:
        return (cdir, version)
    cdir = repository.version_directory(version)
    if cdir is None:
        download_hcd_version(version, verbose=verbose)
        cdir = repository.version_directory(version)
    return (cdir, version)


def get_hcd_version(install_dir):
    for root, dirs, files in os.walk(install_dir):
        for file in files:
            match = re.search('^hcd(?:-core)?-([0-9.]+)(?:-.*)?\.jar', file)
            if match:
                return match.group(1)
    return None


def get_hcd_cassandra_version(install_dir):
    hcd_cmd = os.path.join(install_dir, 'bin', 'hcd')
    (output, stderr) = subprocess.Popen([hcd_cmd, "cassandra", '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    # just take the last line to avoid any possible logback log lines
    output = output.decode('utf-8').rstrip().split('\n')[-1]
    match = re.search('([0-9.]+)(?:-.*)?', str(output))
    if match:
        return LooseVersion(match.group(1))
    raise ArgumentError("Unable to determine Cassandra version in: %s.\n\tstdout: '%s'\n\tstderr: '%s'"
                        % (install_dir, output, stderr))
