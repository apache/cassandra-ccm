CCM (Cassandra Cluster Manager)
====================================================


New to Python development?
--------------------------
Python has moved on since CCM started development. `pip` is the new `easy_install`,
Python 3 is the new 2.7, and pyenv and virtualenv are strongly recommended for managing
multiple Python versions and dependencies for specific Python applications.

A typical macOS setup would be to install [Homebrew](https://docs.brew.sh/Installation),
then `brew install pyenv` to manage Python versions and then use virtualenv to
manage the dependencies for CCM. Make sure to add [brew's bin directory to your path in
your ~/.zshenv](https://www.zerotohero.dev/zshell-startup-files/). This would be
`/usr/local` for macOS Intel and `/opt/homebrew/` for macOS on Apple Silicon.

Now you are ready to install Python using pyenv. To avoid getting a bleeding edge version that will fail with 
some aspect of CCM you can `pyenv install 3.9.16`.

To create the virtualenv run `python3 -m venv --prompt ccm venv` with your git repo as the
current working directory to create a virtual environment for CCM. Then `source venv/bin/activate` to
enable the venv for the current terminal and `deactivate` to exit.

Now you a ready to set up the venv with CCM and its test dependencies. `pip install -e <path_to_ccm_repo>`
to install CCM, and its runtime dependencies from `requirements.txt`, so that the version of
CCM you are running points to the code you are actively working on. There is no build or package step because you
are editing the Python files being run every time you invoke CCM.

Almost there. Now you just need to add the test dependencies that are not in `requirements.txt`.
`pip install mock pytest requests` to finish setting up your dev environment!

Another caveat that has recently appeared in Cassandra versions 4.0 and below is they all ship with a version of JNA that isn't
compatible with Apple Silicon and there are no plans to update JNA on those versions. One work around if you are
generally building Cassandra from source to use with CCM is to replace the JNA jar in your Maven repo with a [newer
one](https://search.maven.org/artifact/net.java.dev.jna/jna/5.8.0/jar) that supports Apple Silicon.
Which you version you need to replace will vary depending on the Cassandra version, but it will normally be in
`~/.m2/repository/net/java/dev/jna/jna/<someversion>`. You can also replace the library in
`~/.ccm/repository/<whatever>/lib`.

Also don't forget to disable `AirPlay Receiver` on macOS which also listens on port `7000`.

Requirements
------------

- A working python installation (tested to work with python 2.7).
- See `requirements.txt` for runtime requirements
- `mock` and `pytest` for tests
- ant (http://ant.apache.org/, on macOS X, `brew install ant`)
- Java: Cassandra currently builds with either 8 or 11 and is restricted to JDK 8 language
  features and dependencies. There are several sources for the JDK and Azul Zulu is one good option.
- If you want to create multiple node clusters, the simplest way is to use
  multiple loopback aliases. On modern linux distributions you probably don't
  need to do anything, but on macOS X, you will need to create the aliases with

      sudo ifconfig lo0 alias 127.0.0.2 up
      sudo ifconfig lo0 alias 127.0.0.3 up
      ...

  Note that the usage section assumes that at least 127.0.0.1, 127.0.0.2 and
  127.0.0.3 are available.

### Optional Requirements

- Paramiko (http://www.paramiko.org/): Paramiko adds the ability to execute CCM
                                       remotely; `pip install paramiko`

__Note__: The remote machine must be configured with an SSH server and a working
          CCM. When working with multiple nodes each exposed IP address must be
          in sequential order. For example, the last number in the 4th octet of
          a IPv4 address must start with `1` (e.g. 192.168.33.11). See
          [Vagrantfile](misc/Vagrantfile) for help with configuration of remote
          CCM machine.


Known issues
------------
Windows only:
  - `node start` pops up a window, stealing focus.
  - cqlsh started from ccm show incorrect prompts on command-prompt
  - non nodetool-based command-line options fail (sstablesplit, scrub, etc)
  - To install psutil, you must use the .msi from pypi. pip install psutil will not work
  - You will need ant.bat in your PATH in order to build C* from source
  - You must run with an Unrestricted Powershell Execution-Policy if using Cassandra 2.1.0+
  - Ant installed via [chocolatey](https://chocolatey.org/) will not be found by ccm, so you must create a symbolic
    link in order to fix the issue (as administrator):
    - cmd /c mklink C:\ProgramData\chocolatey\bin\ant.bat C:\ProgramData\chocolatey\bin\ant.exe

macOS only:
  - Airplay listens for incoming connections on 7000 so disable `Settings` -> `General` -> `AirDrop & Handoff` -> `AirPlay Receiver`

Remote Execution only:
  - Using `--config-dir` and `--install-dir` with `create` may not work as
    expected; since the configuration directory and the installation directory
    contain lots of files they will not be copied over to the remote machine
    like most other options for cluster and node operations
  - cqlsh started from ccm using remote execution will not start
    properly (e.g.`ccm --ssh-host 192.168.33.11 node1 cqlsh`); however
    `-x <CMDS>` or `--exec=CMDS` can still be used to execute a CQLSH command
    on a remote node.

Installation
------------

ccm uses python distutils so from the source directory run:

    sudo ./setup.py install

ccm is available on the [Python Package Index][pip]:

    pip install ccm

There is also a [Homebrew package][brew] available:

    brew install ccm

  [pip]: https://pypi.org/project/ccm/
  [brew]: https://github.com/Homebrew/homebrew-core/blob/master/Formula/ccm.rb


Testing
-----------------------

Create a virtual environment i.e.:

    python3 -m venv ccm

`pip install` all dependencies as well as `mock` and `pytest`. Run `pytest` from the repository root to run the tests.


CCM Lib
-------

The ccm facilities are available programmatically through ccmlib. This could
be used to implement automated tests against Cassandra. A simple example of
how to use ccmlib follows:

    import ccmlib.cluster

    CLUSTER_PATH="."
    cluster = ccmlib.cluster.Cluster(CLUSTER_PATH, 'test', cassandra_version='2.1.14')
    cluster.populate(3).start()
    [node1, node2, node3] = cluster.nodelist()

    # do some tests on the cluster/nodes. To connect to a node through thrift,
    # the host and port to a node is available through
    #   node.network_interfaces['thrift']

    cluster.flush()
    node2.compact()

    # do some other tests

    # after the test, you can leave the cluster running, you can stop all nodes
    # using cluster.stop() but keep the data around (in CLUSTER_PATH/test), or
    # you can remove everything with cluster.remove()
