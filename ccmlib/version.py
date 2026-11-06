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

from __future__ import absolute_import

import re
from functools import total_ordering

from packaging.version import InvalidVersion, Version


_legacy_version_component_re = re.compile(r"(\d+ | [a-z]+ | \.| -)", re.VERBOSE)

_legacy_version_replacement_map = {
    "pre": "c",
    "preview": "c",
    "-": "final-",
    "rc": "c",
    "dev": "@",
}


def _parse_legacy_version_parts(s):
    for part in _legacy_version_component_re.split(s):
        part = _legacy_version_replacement_map.get(part, part)

        if not part or part == ".":
            continue

        if part[:1] in "0123456789":
            # pad for numeric comparison
            yield part.zfill(8)
        else:
            yield "*" + part

    # ensure that alpha/beta/candidate are before final
    yield "*final"


def _legacy_cmpkey(version):
    parts = []
    for part in _parse_legacy_version_parts(version.lower()):
        if part.startswith("*"):
            # remove "-" before a prerelease tag
            if part < "*final":
                while parts and parts[-1] == "*final-":
                    parts.pop()

            # remove trailing zeros from each series of numeric parts
            while parts and parts[-1] == "00000000":
                parts.pop()

        parts.append(part)

    return tuple(parts)


class _LegacyVersion(object):
    """
    Fallback for version strings that are not valid PEP 440 (e.g. ``4.0-SNAPSHOT``).

    Ported from packaging<22, which removed ``LegacyVersion``. Newer setuptools
    requires a recent packaging, so we can't simply pin packaging to an old release.
    """

    __slots__ = ("_version", "_key")

    def __init__(self, version):
        self._version = str(version)
        self._key = _legacy_cmpkey(self._version)

    def __str__(self):
        return self._version

    @property
    def release(self):
        return None


def parse(version):
    try:
        return Version(version)
    except InvalidVersion:
        return _LegacyVersion(version)


def _sort_key(inner):
    # Legacy versions always sort before PEP 440 versions, as they did in packaging<22
    if isinstance(inner, _LegacyVersion):
        return (0, inner._key)  # pylint: disable=protected-access
    return (1, inner)


@total_ordering
class LooseVersion(object):
    """
    Lightweight compatibility wrapper to replace distutils.version.LooseVersion.

    It delegates comparison/ordering to packaging.version (with a legacy fallback) while exposing
    ``version`` and ``vstring`` attributes that the existing code expects.
    """

    __slots__ = ("_inner",)

    def __init__(self, version):
        if isinstance(version, LooseVersion):
            self._inner = version._inner  # pylint: disable=protected-access
        else:
            self._inner = parse(str(version))

    def __repr__(self):
        return "LooseVersion({})".format(str(self._inner))

    def __str__(self):
        return str(self._inner)

    def __hash__(self):
        return hash(_sort_key(self._inner))

    def _coerce_other(self, other):
        if isinstance(other, LooseVersion):
            return other._inner  # pylint: disable=protected-access
        return parse(str(other))

    def __eq__(self, other):
        return _sort_key(self._inner) == _sort_key(self._coerce_other(other))

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        return _sort_key(self._inner) < _sort_key(self._coerce_other(other))

    @property
    def vstring(self):
        return str(self._inner)

    @property
    def version(self):
        release = getattr(self._inner, "release", None)
        if release:
            return release

        # Fallback for legacy version objects without a release tuple
        parts = re.split(r"\D+", str(self._inner))
        return tuple(int(p) for p in parts if p)
