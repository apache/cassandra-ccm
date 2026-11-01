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


import configparser
import functools
import io
import os
import ssl
import subprocess
import tarfile
import threading
import time
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest
from six.moves import urllib

from ccmlib import repository

PAYLOAD = bytes(range(256)) * 256
STALL_SECONDS = 5
SSL_DIR = os.path.join(os.path.dirname(__file__), '..', 'ssl')


class _MirrorHandler(BaseHTTPRequestHandler):
    """Serves the payload, misbehaving as the first path segment says"""

    def do_GET(self):
        requests = self.server.requests
        requests.append(self.path)
        behaviour = self.path.split('/')[1]
        first = requests.count(self.path) == 1
        payload = self.server.payload

        if behaviour == 'missing':
            self.send_error(404)
            return
        if behaviour == 'error-once' and first:
            self.send_error(500)
            return

        self.send_response(200)
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        if behaviour == 'stall-always' or (behaviour == 'stall-once' and first):
            self.wfile.write(payload[:len(payload) // 2])
            self.wfile.flush()
            time.sleep(STALL_SECONDS)
        elif behaviour == 'truncate-once' and first:
            # HTTP/1.0: the connection closes when the handler returns
            self.wfile.write(payload[:len(payload) // 2])
        else:
            self.wfile.write(payload)

    def log_message(self, *args):
        pass


class _MirrorServer(ThreadingHTTPServer):
    block_on_close = False  # do not wait for stalled handlers

    def __init__(self, context=None):
        ThreadingHTTPServer.__init__(self, ('127.0.0.1', 0), _MirrorHandler)
        if context is not None:
            self.socket = context.wrap_socket(self.socket, server_side=True)
        self.connections = 0
        self.requests = []
        self.payload = PAYLOAD
        self.base = '{}://127.0.0.1:{}'.format('https' if context else 'http', self.server_address[1])

    def get_request(self):
        # counted before the TLS handshake, which never reaches the handler when it fails
        self.connections += 1
        return ThreadingHTTPServer.get_request(self)


def _serve(server):
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def mirror():
    yield from _serve(_MirrorServer())


@pytest.fixture
def untrusted_mirror():
    # self-signed and long expired, so no client verifies it
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(os.path.join(SSL_DIR, 'client_cert.pem'), os.path.join(SSL_DIR, 'client_key.pem'))
    yield from _serve(_MirrorServer(context))


class _GitRemoteHandler(SimpleHTTPRequestHandler):
    """
    Serves git repositories over git's dumb http protocol. Every git command starts by requesting info/refs,
    and that request misbehaves as the next entry of server.misbehave says.
    """

    def do_GET(self):
        if '/info/refs' in self.path:
            self.server.refs_requests += 1
            behaviour = self.server.misbehave.pop(0) if self.server.misbehave else None
            if behaviour == 'error':
                self.send_error(500)
                return
            if behaviour == 'stall':
                self.send_response(200)
                self.send_header('Content-Length', '1000000')
                self.end_headers()
                time.sleep(STALL_SECONDS)
                return
        SimpleHTTPRequestHandler.do_GET(self)

    def log_message(self, *args):
        pass


class _GitRemoteServer(ThreadingHTTPServer):
    block_on_close = False  # do not wait for stalled handlers

    def __init__(self, directory):
        ThreadingHTTPServer.__init__(self, ('127.0.0.1', 0), functools.partial(_GitRemoteHandler, directory=directory))
        self.refs_requests = 0
        self.misbehave = []
        self.url = 'http://127.0.0.1:{}/cassandra.git'.format(self.server_address[1])


def _git(*args):
    subprocess.check_call(('git',) + args, stdout=subprocess.DEVNULL)


@pytest.fixture
def git_remote(tmp_path, monkeypatch):
    """A repository with a cassandra-4.0 branch served over http, with ccm's repository directory in tmp_path"""
    source, served = str(tmp_path / 'source'), str(tmp_path / 'served' / 'cassandra.git')
    _git('init', '-q', source)
    _git('-C', source, 'symbolic-ref', 'HEAD', 'refs/heads/cassandra-4.0')
    _git('-C', source, '-c', 'user.name=ccm', '-c', 'user.email=ccm@example.com', '-c', 'commit.gpgsign=false',
         'commit', '-q', '--allow-empty', '-m', 'initial')
    _git('clone', '-q', '--bare', source, served)
    _git('-C', served, 'update-server-info')
    monkeypatch.setattr(repository, 'get_default_path', lambda: str(tmp_path))
    monkeypatch.setattr(repository, 'compile_version', lambda *args: None)
    yield from _serve(_GitRemoteServer(str(tmp_path / 'served')))


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr(repository, 'DOWNLOAD_TIMEOUT', 0.5)
    monkeypatch.setattr(repository, 'DOWNLOAD_RETRY_DELAY', 0)
    monkeypatch.setattr(repository, 'GIT_RETRY_DELAY_SEC', 0)
    monkeypatch.setattr(repository, 'GIT_STALL_TIMEOUT_SEC', 2)
    monkeypatch.setattr(repository, '_git_remote_down', False)


def _read(path):
    with open(path, 'rb') as f:
        return f.read()


def test_missing_url_falls_through_to_next_without_retry(mirror, tmp_path):
    target = str(tmp_path / 'download')
    repository.__download_from_first([mirror.base + '/missing/f', mirror.base + '/ok/f'], target)

    assert _read(target) == PAYLOAD
    assert mirror.requests == ['/missing/f', '/ok/f']


def test_stalled_connection_times_out_and_is_retried(mirror, tmp_path):
    target = str(tmp_path / 'download')
    start = time.time()
    repository.__download_from_first([mirror.base + '/stall-once/f'], target)

    assert _read(target) == PAYLOAD
    assert mirror.requests == ['/stall-once/f'] * 2
    assert time.time() - start < STALL_SECONDS


def test_truncated_response_is_retried(mirror, tmp_path):
    target = str(tmp_path / 'download')
    repository.__download_from_first([mirror.base + '/truncate-once/f'], target)

    assert _read(target) == PAYLOAD
    assert mirror.requests == ['/truncate-once/f'] * 2


def test_server_error_is_retried(mirror, tmp_path):
    target = str(tmp_path / 'download')
    repository.__download_from_first([mirror.base + '/error-once/f'], target)

    assert _read(target) == PAYLOAD
    assert mirror.requests == ['/error-once/f'] * 2


def test_url_that_keeps_failing_falls_through_to_next(mirror, tmp_path):
    target = str(tmp_path / 'download')
    repository.__download_from_first([mirror.base + '/stall-always/f', mirror.base + '/ok/f'], target)

    assert _read(target) == PAYLOAD
    assert mirror.requests == ['/stall-always/f'] * repository.DOWNLOAD_ATTEMPTS + ['/ok/f']


def test_untrusted_certificate_falls_through_to_next_without_retry(untrusted_mirror, mirror, tmp_path):
    target = str(tmp_path / 'download')
    repository.__download_from_first([untrusted_mirror.base + '/ok/f', mirror.base + '/ok/f'], target)

    assert _read(target) == PAYLOAD
    assert untrusted_mirror.connections == 1
    assert mirror.requests == ['/ok/f']


def test_last_error_is_raised_when_no_url_works(mirror, tmp_path):
    target = str(tmp_path / 'download')
    with pytest.raises(urllib.error.HTTPError) as e:
        repository.__download_from_first([mirror.base + '/missing/a', mirror.base + '/missing/b'], target)

    assert e.value.code == 404
    assert mirror.requests == ['/missing/a', '/missing/b']


def test_download_version_tries_mirrors_in_order(mirror, tmp_path, monkeypatch):
    tarball = io.BytesIO()
    with tarfile.open(fileobj=tarball, mode='w:gz') as tar:
        script = tarfile.TarInfo('apache-cassandra-9.9.9/bin/cassandra')
        script.size = len(PAYLOAD)
        tar.addfile(script, io.BytesIO(PAYLOAD))
    mirror.payload = tarball.getvalue()
    monkeypatch.setattr(repository, 'MIRRORS', [mirror.base + '/missing', mirror.base + '/ok'])
    monkeypatch.setattr(repository, 'CCM_CONFIG', configparser.RawConfigParser())
    monkeypatch.setattr(repository, 'get_default_path', lambda: str(tmp_path))

    repository.download_version('9.9.9', binary=True)

    assert mirror.requests == ['/missing/9.9.9/apache-cassandra-9.9.9-bin.tar.gz',
                               '/ok/9.9.9/apache-cassandra-9.9.9-bin.tar.gz']
    installed = tmp_path / 'repository' / '9.9.9'
    assert _read(str(installed / 'bin' / 'cassandra')) == PAYLOAD
    assert _read(str(installed / '0.version.txt')) == b'9.9.9'


GITHUB_VERSION = 'github:apache/cassandra-4.0'


def test_git_clone_from_remote_is_retried(git_remote):
    git_remote.misbehave = ['error']
    repository.clone_development(git_remote.url, GITHUB_VERSION)

    assert git_remote.refs_requests == 2
    assert os.path.isdir(os.path.join(repository.directory_name(GITHUB_VERSION), '.git'))


def test_stalled_git_fetch_is_abandoned_and_retried(git_remote):
    repository.clone_development(git_remote.url, GITHUB_VERSION)
    git_remote.misbehave = ['stall']
    start = time.time()
    repository.clone_development(git_remote.url, GITHUB_VERSION)

    assert git_remote.refs_requests == 3
    assert time.time() - start < STALL_SECONDS


def test_git_error_is_reported_once_attempts_run_out(git_remote):
    git_remote.misbehave = ['error'] * repository.GIT_ATTEMPTS
    with pytest.raises(AssertionError) as e:
        repository.clone_development(git_remote.url, GITHUB_VERSION)

    assert str(e.value).startswith("Could not do a git clone: fatal: unable to access '{}/'".format(git_remote.url))
    assert str(e.value).endswith('500')
    assert git_remote.refs_requests == repository.GIT_ATTEMPTS


def test_unreachable_remote_is_tried_once_until_it_works_again(git_remote):
    git_remote.misbehave = ['error'] * (repository.GIT_ATTEMPTS + 1)
    with pytest.raises(AssertionError):
        repository.clone_development(git_remote.url, GITHUB_VERSION)
    with pytest.raises(AssertionError):
        repository.clone_development(git_remote.url, GITHUB_VERSION)
    assert git_remote.refs_requests == repository.GIT_ATTEMPTS + 1

    repository.clone_development(git_remote.url, GITHUB_VERSION)
    assert git_remote.refs_requests == repository.GIT_ATTEMPTS + 2

    # the remote works again, so its next failure is retried, this time by the fetch into the cache
    git_remote.misbehave = ['error']
    repository.clone_development(git_remote.url, GITHUB_VERSION)
    assert git_remote.refs_requests == repository.GIT_ATTEMPTS + 4


def test_local_repository_is_not_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, 'get_default_path', lambda: str(tmp_path))
    monkeypatch.setattr(repository, 'GIT_RETRY_DELAY_SEC', 60)
    missing = str(tmp_path / 'missing')
    start = time.time()
    with pytest.raises(AssertionError) as e:
        repository.clone_development(missing, 'local:{}:trunk'.format(missing))

    assert 'does not exist' in str(e.value)
    assert time.time() - start < STALL_SECONDS
