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


import unittest

from ccmlib.version import LooseVersion


class TestLooseVersion(unittest.TestCase):

    def test_pep440_versions(self):
        self.assertEqual(str(LooseVersion('5.0-alpha1')), '5.0a1')
        self.assertEqual(LooseVersion('5.0-alpha1').version, (5, 0))
        self.assertLess(LooseVersion('5.0-alpha1'), LooseVersion('5.0-beta2'))
        self.assertLess(LooseVersion('5.0-rc1'), LooseVersion('5.0'))
        self.assertLess(LooseVersion('3.11.17'), LooseVersion('4.0'))
        self.assertEqual(LooseVersion('4.0'), LooseVersion(4.0))
        self.assertEqual(LooseVersion('4.0'), '4.0')

    def test_legacy_versions(self):
        # Not valid PEP 440; these must not raise with packaging>=22
        snapshot = LooseVersion('4.0.1-SNAPSHOT')
        self.assertEqual(str(snapshot), '4.0.1-SNAPSHOT')
        self.assertEqual(snapshot.vstring, '4.0.1-SNAPSHOT')
        self.assertEqual(snapshot.version, (4, 0, 1))
        self.assertEqual(LooseVersion('6.0-alpha1-SNAPSHOT').version, (6, 0, 1))
        self.assertEqual(snapshot, LooseVersion('4.0.1-SNAPSHOT'))
        self.assertEqual(hash(snapshot), hash(LooseVersion('4.0.1-SNAPSHOT')))
        self.assertLess(LooseVersion('4.0-SNAPSHOT'), LooseVersion('4.0.1-SNAPSHOT'))
        self.assertLess(LooseVersion('6.8.0-SNAPSHOT'), LooseVersion('6.8.1-SNAPSHOT'))

    def test_legacy_versions_sort_before_pep440(self):
        # Matches packaging<22 LegacyVersion ordering
        self.assertLess(LooseVersion('4.0-SNAPSHOT'), LooseVersion('1.0'))
        self.assertNotEqual(LooseVersion('trunk'), LooseVersion('4.0'))
        self.assertEqual(sorted([LooseVersion('4.0'), LooseVersion('trunk')])[0], LooseVersion('trunk'))
