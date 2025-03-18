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
from ccmlib.cmds.cluster_cmds import ClusterCreateCmd
from ccmlib.hcd.hcd_cluster import isHcdClusterType


# static initialisation:  register the extension cluster type, add hcd specific option to ClusterCreateCmd

extension.CLUSTER_TYPES.append(isHcdClusterType)

ClusterCreateCmd.options_list.extend([
    (["--hcd"], {'action': "store_true", 'dest': "hcd", 'help': "Use with -v or --install-dir to indicate that the version being loaded is HCD"})])
