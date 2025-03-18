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


# DataStax Enterprise (DSE) clusters

from __future__ import absolute_import

import os
import re
import shutil
import signal
import subprocess
import tarfile
import tempfile
from argparse import ArgumentError
from distutils.version import LooseVersion
from six.moves import urllib

from ccmlib import common, repository
from ccmlib.cluster import Cluster
from ccmlib.common import rmdirs
from ccmlib.common import ArgumentError
from ccmlib.dse.dse_node import DseNode

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser


DSE_CASSANDRA_CONF_DIR = "resources/cassandra/conf"
OPSCENTER_CONF_DIR = "conf"
DSE_ARCHIVE = "https://downloads.datastax.com/enterprise/dse-%s-bin.tar.gz"
OPSC_ARCHIVE = "https://downloads.datastax.com/enterprise/opscenter-%s.tar.gz"



def isDse(install_dir, options=None):
    if install_dir is None:
        raise ArgumentError('Undefined installation directory')
    bin_dir = os.path.join(install_dir, common.BIN_DIR)
    if options and options.dse and './' != install_dir and not os.path.exists(bin_dir):
        raise ArgumentError('Installation directory does not contain a bin directory: %s' % install_dir)
    if options and options.dse:
        return True
    dse_script = os.path.join(bin_dir, 'dse')
    if options and not options.dse and './' != install_dir and os.path.exists(dse_script):
        raise ArgumentError('Installation directory is DSE but options did not specify `--dse`: %s' % install_dir)
    return os.path.exists(dse_script)


def isOpscenter(install_dir, options=None):
    if install_dir is None:
        raise ArgumentError('Undefined installation directory')
    bin_dir = os.path.join(install_dir, common.BIN_DIR)
    if options and options.dse and './' != install_dir and not os.path.exists(bin_dir):
        raise ArgumentError('Installation directory does not contain a bin directory')
    opscenter_script = os.path.join(bin_dir, 'opscenter')
    return os.path.exists(opscenter_script)


def isDseClusterType(install_dir, options=None):
    if isDse(install_dir, options) or isOpscenter(install_dir, options):
        return DseCluster
    return None


class DseCluster(Cluster):

    @staticmethod
    def getConfDir(install_dir):
        if isDse(install_dir):
            return os.path.join(install_dir, DSE_CASSANDRA_CONF_DIR)
        elif isOpscenter(install_dir):
            return  os.path.join(os.path.join(install_dir, OPSCENTER_CONF_DIR), common.CASSANDRA_CONF)
        raise RuntimeError("illegal call to DseCluster.getConfDir() when not dse or opscenter")

    @staticmethod
    def getNodeClass():
        return DseNode


    def __init__(self, path, name, partitioner=None, install_dir=None, create_directory=True, version=None, verbose=False, derived_cassandra_version=None, options=None):
        self.load_credentials_from_file(options.dse_credentials_file if options else None)
        self.dse_username = options.dse_username if options else None
        self.dse_password = options.dse_password if options else None
        self.opscenter = options.opscenter if options else None
        self._cassandra_version = None
        self._cassandra_version = derived_cassandra_version

        super(DseCluster, self).__init__(path, name, partitioner, install_dir, create_directory, version, verbose, options=options)

    def load_from_repository(self, version, verbose):
        if self.opscenter is not None:
            odir = setup_opscenter(self.opscenter, self.dse_username, self.dse_password, verbose)
            target_dir = os.path.join(self.get_path(), 'opscenter')
            shutil.copytree(odir, target_dir)
        return setup_dse(version, self.dse_username, self.dse_password, verbose)

    def load_credentials_from_file(self, dse_credentials_file):
        # Use .dse.ini if it exists in the default .ccm directory.
        if dse_credentials_file is None:
            creds_file = os.path.join(common.get_default_path(), '.dse.ini')
            if os.path.isfile(creds_file):
                dse_credentials_file = creds_file

        if dse_credentials_file is not None:
            parser = ConfigParser.RawConfigParser()
            parser.read(dse_credentials_file)
            if parser.has_section('dse_credentials'):
                if parser.has_option('dse_credentials', 'dse_username'):
                    self.dse_username = parser.get('dse_credentials', 'dse_username')
                if parser.has_option('dse_credentials', 'dse_password'):
                    self.dse_password = parser.get('dse_credentials', 'dse_password')
            else:
                common.warning("{} does not contain a 'dse_credentials' section.".format(dse_credentials_file))

    def get_seeds(self):
        return [s.network_interfaces['storage'][0] if isinstance(s, DseNode) else s for s in self.seeds]

    def hasOpscenter(self):
        return os.path.exists(os.path.join(self.get_path(), 'opscenter'))

    def create_node(self, name, auto_bootstrap, thrift_interface, storage_interface, jmx_port, remote_debug_port, initial_token, save=True, binary_interface=None, byteman_port='0', environment_variables=None,derived_cassandra_version=None):
        return DseNode(name, self, auto_bootstrap, thrift_interface, storage_interface, jmx_port, remote_debug_port, initial_token, save, binary_interface, byteman_port, environment_variables=environment_variables, derived_cassandra_version=derived_cassandra_version)

    def can_generate_tokens(self):
        return False

    def start(self, no_wait=False, verbose=False, wait_for_binary_proto=False, wait_other_notice=True, jvm_args=None, profile_options=None, quiet_start=False, allow_root=False, jvm_version=None):
        if jvm_args is None:
            jvm_args = []
        marks = {}
        for node in self.nodelist():
            marks[node] = node.mark_log()
        started = super(DseCluster, self).start(no_wait, verbose, wait_for_binary_proto, wait_other_notice, jvm_args, profile_options, quiet_start=quiet_start, allow_root=allow_root, timeout=180, jvm_version=jvm_version)
        self.start_opscenter()
        if self._misc_config_options.get('enable_aoss', False):
            self.wait_for_any_log('AlwaysOn SQL started', 600, marks=marks)
        return started

    def stop(self, wait=True, signal_event=signal.SIGTERM, **kwargs):
        not_running = super(DseCluster, self).stop(wait=wait, signal_event=signal.SIGTERM, **kwargs)
        self.stop_opscenter()
        return not_running

    def remove(self, node=None):
        # We _must_ gracefully stop if aoss is enabled, otherwise we will leak the spark workers
        super(DseCluster, self).remove(node=node, gently=self._misc_config_options.get('enable_aoss', False))

    def cassandra_version(self):
        if self._cassandra_version is None:
            self._cassandra_version = get_dse_cassandra_version(self.get_install_dir())
        return self._cassandra_version

    def enable_aoss(self):
        if self.version() < '6.0':
            common.error("Cannot enable AOSS in DSE clusters before 6.0")
            exit(1)
        self._misc_config_options['enable_aoss'] = True
        for node in self.nodelist():
            port_offset = int(node.name[4:])
            node.enable_aoss(thrift_port=10000 + port_offset, web_ui_port=9077 + port_offset)
        self._update_config()

    def set_dse_configuration_options(self, values=None):
        if values is not None:
            self._dse_config_options = common.merge_configuration(self._dse_config_options, values)
        self._update_config()
        for node in list(self.nodes.values()):
            node.import_dse_config_files()
        return self

    def start_opscenter(self):
        if self.hasOpscenter():
            self.write_opscenter_cluster_config()
            args = [os.path.join(self.get_path(), 'opscenter', 'bin', common.platform_binary('opscenter'))]
            subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def stop_opscenter(self):
        pidfile = os.path.join(self.get_path(), 'opscenter', 'twistd.pid')
        if os.path.exists(pidfile):
            with open(pidfile, 'r') as f:
                pid = int(f.readline().strip())
                f.close()
            if pid is not None:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
            os.remove(pidfile)

    def write_opscenter_cluster_config(self):
        cluster_conf = os.path.join(self.get_path(), 'opscenter', 'conf', 'clusters')
        if not os.path.exists(cluster_conf):
            os.makedirs(cluster_conf)
            if len(self.nodes) > 0:
                node = list(self.nodes.values())[0]
                (node_ip, node_port) = node.network_interfaces['thrift']
                node_jmx = node.jmx_port
                with open(os.path.join(cluster_conf, self.name + '.conf'), 'w+') as f:
                    f.write('[jmx]\n')
                    f.write('port = %s\n' % node_jmx)
                    f.write('[cassandra]\n')
                    f.write('seed_hosts = %s\n' % node_ip)
                    f.write('api_port = %s\n' % node_port)
                    f.close()


def setup_dse(version, username, password, verbose=False):
    (cdir, version, fallback) = repository.__setup(version, verbose)
    if cdir:
        return (cdir, version)
    cdir = repository.version_directory(version)
    if cdir is None:
        download_dse_version(version, username, password, verbose=verbose)
        cdir = repository.version_directory(version)
    return (cdir, version)


def setup_opscenter(opscenter, username, password, verbose=False):
    ops_version = 'opsc' + opscenter
    odir = repository.version_directory(ops_version)
    if odir is None:
        download_opscenter_version(opscenter, username, password, ops_version, verbose=verbose)
        odir = repository.version_directory(ops_version)
    return odir


def get_dse_cassandra_version(install_dir):
    dse_cmd = os.path.join(install_dir, 'bin', 'dse')
    (output, stderr) = subprocess.Popen([dse_cmd, "cassandra", '-v'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    # just take the last line to avoid any possible log lines
    output = output.decode('utf-8').rstrip().split('\n')[-1]
    match = re.search('([0-9.]+)(?:-.*)?', str(output))
    if match:
        return LooseVersion(match.group(1))
    raise ArgumentError("Unable to determine Cassandra version in: %s.\n\tstdout: '%s'\n\tstderr: '%s'"
                        % (install_dir, output, stderr))


def download_dse_version(version, username, password, verbose=False):
    url = DSE_ARCHIVE
    if repository.CCM_CONFIG.has_option('repositories', 'dse'):
        url = repository.CCM_CONFIG.get('repositories', 'dse')

    url = url % version
    _, target = tempfile.mkstemp(suffix=".tar.gz", prefix="ccm-")
    try:
        if username is None:
            common.warning("No dse username detected, specify one using --dse-username or passing in a credentials file using --dse-credentials.")
        if password is None:
            common.warning("No dse password detected, specify one using --dse-password or passing in a credentials file using --dse-credentials.")
        repository.__download(url, target, username=username, password=password, show_progress=verbose)
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


def download_opscenter_version(version, username, password, target_version, verbose=False):
    url = OPSC_ARCHIVE
    if repository.CCM_CONFIG.has_option('repositories', 'opscenter'):
        url = repository.CCM_CONFIG.get('repositories', 'opscenter')

    url = url % version
    _, target = tempfile.mkstemp(suffix=".tar.gz", prefix="ccm-")
    try:
        if username is None:
            common.warning("No dse username detected, specify one using --dse-username or passing in a credentials file using --dse-credentials.")
        if password is None:
            common.warning("No dse password detected, specify one using --dse-password or passing in a credentials file using --dse-credentials.")
        repository.__download(url, target, username=username, password=password, show_progress=verbose)
        common.info("Extracting {} as version {} ...".format(target, target_version))
        tar = tarfile.open(target)
        dir = tar.next().name.split("/")[0]  # pylint: disable=all
        tar.extractall(path=repository.__get_dir())
        tar.close()
        target_dir = os.path.join(repository.__get_dir(), target_version)
        if os.path.exists(target_dir):
            rmdirs(target_dir)
        shutil.move(os.path.join(repository.__get_dir(), dir), target_dir)
    except urllib.error.URLError as e:
        msg = "Invalid version {}".format(version) if url is None else "Invalid url {}".format(url)
        msg = msg + " (underlying error is: {})".format(str(e))
        raise ArgumentError(msg)
    except tarfile.ReadError as e:
        raise ArgumentError("Unable to uncompress downloaded file: {}".format(str(e)))
