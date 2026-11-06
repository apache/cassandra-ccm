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
import warnings
from functools import total_ordering

from packaging.version import InvalidVersion, Version


# BEGIN copied verbatim from packaging 20.9 (dual licensed Apache-2.0 / BSD), which still had
# LegacyVersion for version strings that are not PEP 440 (e.g. 4.0-SNAPSHOT). packaging>=22
# removed it, but newer setuptools requires a newer packaging, so we can't pin an old one.
#   parse():                        https://github.com/pypa/packaging/blob/20.9/packaging/version.py#L49-L59
#   _BaseVersion .. _legacy_cmpkey: https://github.com/pypa/packaging/blob/20.9/packaging/version.py#L68-L251

def parse(version):
    # type: (str) -> Union[LegacyVersion, Version]
    """
    Parse the given version string and return either a :class:`Version` object
    or a :class:`LegacyVersion` object depending on if the given version is
    a valid PEP 440 version or a legacy version.
    """
    try:
        return Version(version)
    except InvalidVersion:
        return LegacyVersion(version)


class _BaseVersion(object):
    _key = None  # type: Union[CmpKey, LegacyCmpKey]

    def __hash__(self):
        # type: () -> int
        return hash(self._key)

    # Please keep the duplicated `isinstance` check
    # in the six comparisons hereunder
    # unless you find a way to avoid adding overhead function calls.
    def __lt__(self, other):
        # type: (_BaseVersion) -> bool
        if not isinstance(other, _BaseVersion):
            return NotImplemented

        return self._key < other._key

    def __le__(self, other):
        # type: (_BaseVersion) -> bool
        if not isinstance(other, _BaseVersion):
            return NotImplemented

        return self._key <= other._key

    def __eq__(self, other):
        # type: (object) -> bool
        if not isinstance(other, _BaseVersion):
            return NotImplemented

        return self._key == other._key

    def __ge__(self, other):
        # type: (_BaseVersion) -> bool
        if not isinstance(other, _BaseVersion):
            return NotImplemented

        return self._key >= other._key

    def __gt__(self, other):
        # type: (_BaseVersion) -> bool
        if not isinstance(other, _BaseVersion):
            return NotImplemented

        return self._key > other._key

    def __ne__(self, other):
        # type: (object) -> bool
        if not isinstance(other, _BaseVersion):
            return NotImplemented

        return self._key != other._key


class LegacyVersion(_BaseVersion):
    def __init__(self, version):
        # type: (str) -> None
        self._version = str(version)
        self._key = _legacy_cmpkey(self._version)

        warnings.warn(
            "Creating a LegacyVersion has been deprecated and will be "
            "removed in the next major release",
            DeprecationWarning,
        )

    def __str__(self):
        # type: () -> str
        return self._version

    def __repr__(self):
        # type: () -> str
        return "<LegacyVersion({0})>".format(repr(str(self)))

    @property
    def public(self):
        # type: () -> str
        return self._version

    @property
    def base_version(self):
        # type: () -> str
        return self._version

    @property
    def epoch(self):
        # type: () -> int
        return -1

    @property
    def release(self):
        # type: () -> None
        return None

    @property
    def pre(self):
        # type: () -> None
        return None

    @property
    def post(self):
        # type: () -> None
        return None

    @property
    def dev(self):
        # type: () -> None
        return None

    @property
    def local(self):
        # type: () -> None
        return None

    @property
    def is_prerelease(self):
        # type: () -> bool
        return False

    @property
    def is_postrelease(self):
        # type: () -> bool
        return False

    @property
    def is_devrelease(self):
        # type: () -> bool
        return False


_legacy_version_component_re = re.compile(r"(\d+ | [a-z]+ | \.| -)", re.VERBOSE)

_legacy_version_replacement_map = {
    "pre": "c",
    "preview": "c",
    "-": "final-",
    "rc": "c",
    "dev": "@",
}


def _parse_version_parts(s):
    # type: (str) -> Iterator[str]
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
    # type: (str) -> LegacyCmpKey

    # We hardcode an epoch of -1 here. A PEP 440 version can only have a epoch
    # greater than or equal to 0. This will effectively put the LegacyVersion,
    # which uses the defacto standard originally implemented by setuptools,
    # as before all PEP 440 versions.
    epoch = -1

    # This scheme is taken from pkg_resources.parse_version setuptools prior to
    # it's adoption of the packaging library.
    parts = []  # type: List[str]
    for part in _parse_version_parts(version.lower()):
        if part.startswith("*"):
            # remove "-" before a prerelease tag
            if part < "*final":
                while parts and parts[-1] == "*final-":
                    parts.pop()

            # remove trailing zeros from each series of numeric parts
            while parts and parts[-1] == "00000000":
                parts.pop()

        parts.append(part)

    return epoch, tuple(parts)

# END copied verbatim from packaging 20.9


def _sort_key(inner):
    # LegacyVersion and packaging's Version no longer share a base class, so compare them here:
    # legacy versions sort before all PEP 440 versions, as they did in packaging 20.9
    if isinstance(inner, LegacyVersion):
        return (0, inner)
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
