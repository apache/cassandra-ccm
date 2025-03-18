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


from ccmlib import extension
from ccmlib import common
from ccmlib.cmds.cluster_cmds import ClusterAddCmd, ClusterCreateCmd
from ccmlib.dse.dse_cluster import isDseClusterType


# static initialisation:  register the extension cluster type, add dse specific options to ClusterCreateCmd and ClusterAddCmd
extension.CLUSTER_TYPES.append(isDseClusterType)

ClusterCreateCmd.options_list.extend([
    (['-o', "--opsc"], {'type': "string", 'dest': "opscenter", 'help': "Download and use provided OpsCenter version to install with DSE. Will have no effect on cassandra installs)", 'default': None}),
    (["--dse"], {'action': "store_true", 'dest': "dse", 'help': "Use with -v or --install-dir to indicate that the version being loaded is DSE"}),
    (["--dse-username"], {'type': "string", 'dest': "dse_username", 'help': "The username to use to download DSE with", 'default': None}),
    (["--dse-password"], {'type': "string", 'dest': "dse_password", 'help': "The password to use to download DSE with", 'default': None}),
    (["--dse-credentials"], {'type': "string", 'dest': "dse_credentials_file", 'help': "An ini-style config file containing the dse_username and dse_password under a dse_credentials section. [default to {}/.dse.ini if it exists]".format(common.get_default_path_display_name()), 'default': None})])

ClusterAddCmd.options_list.append( (['--dse'], {'action': "store_true", 'dest': "dse_node", 'help': "Add node to DSE Cluster", 'default': False}))
