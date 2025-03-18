CCM (Cassandra Cluster Manager)
====================================================


A script/library to create, launch and remove an Apache Cassandra cluster on
localhost.

The goal of ccm and ccmlib is to make it easy to create, manage and destroy a
small Cassandra cluster on a local box. It is meant for testing a Cassandra cluster.


Installation
------------

See [INSTALL.md](./INSTALL.md).

Usage
-----

Let's say you wanted to fire up a 3 node Cassandra cluster.

### Short version

    ccm create test -v 2.0.5 -n 3 -s

You will of course want to replace `2.0.5` by whichever version of Cassandra
you want to test.

### Longer version

ccm works from a Cassandra source tree (not the jars). There are two ways to
tell ccm how to find the sources:
  1. If you have downloaded *and* compiled Cassandra sources, you can ask ccm
     to use those by initiating a new cluster with:

        ccm create test --install-dir=<path/to/cassandra-sources>

     or, from that source tree directory, simply

          ccm create test

  2. You can ask ccm to use a released version of Cassandra. For instance to
     use Cassandra 2.0.5, run

          ccm create test -v 2.0.5

     ccm will download the binary (from http://archive.apache.org/dist/cassandra),
     and set the new cluster to use it. This means
     that this command can take a few minutes the first time you
     create a cluster for a given version. ccm saves the compiled
     source in `~/.ccm/repository/`, so creating a cluster for that
     version will be much faster the second time you run it
     (note however that if you create a lot of clusters with
     different versions, this will take up disk space).

Once the cluster is created, you can populate it with 3 nodes with:

    ccm populate -n 3

For Mac OSX, create a new interface for every node besides the first, for example if you populated your cluster with 3 nodes, create interfaces for 127.0.0.2 and 127.0.0.3 like so:

    sudo ifconfig lo0 alias 127.0.0.2
    sudo ifconfig lo0 alias 127.0.0.3

Note these aliases will disappear on reboot. For permanent network aliases on Mac OSX see ![Network Aliases](./NETWORK_ALIASES.md).

After that execute:

    ccm start

That will start 3 nodes on IP 127.0.0.[1, 2, 3] on port 9160 for thrift, port
7000 for the internal cluster communication and ports 7100, 7200 and 7300 for JMX.
You can check that the cluster is correctly set up with

    ccm node1 ring

You can then bootstrap a 4th node with

    ccm add node4 -i 127.0.0.4 -j 7400 -b

(populate is just a shortcut for adding multiple nodes initially)

ccm provides a number of conveniences, like flushing all of the nodes of
the cluster:

    ccm flush

or only one node:

    ccm node2 flush

You can also easily look at the log file of a given node with:

    ccm node1 showlog

Finally, you can get rid of the whole cluster (which will stop the node and
remove all the data) with

    ccm remove

The list of other provided commands is available through

    ccm

Each command is then documented through the `-h` (or `--help`) flag. For
instance `ccm add -h` describes the options for `ccm add`.

### Remote Usage (SSH/Paramiko)

All the usage examples above will work exactly the same for a remotely
configured machine; however remote options are required in order to establish a
connection to the remote machine before executing the CCM commands:

| Argument | Value | Description |
| :--- | :--- | :--- |
| --ssh-host | string | Hostname or IP address to use for SSH connection |
| --ssh-port | int | Port to use for SSH connection<br/>Default is 22 |
| --ssh-username | string | Username to use for username/password or public key authentication |
| --ssh-password | string | Password to use for username/password or private key passphrase using public key authentication |
| --ssh-private-key | filename | Private key to use for SSH connection |

#### Special Handling

Some commands require files to be located on the remote server. Those commands
are pre-processed, file transfers are initiated, and updates are made to the
argument value for the remote execution of the CCM command:

| Parameter | Description |
| :--- | :--- |
| `--dse-credentials` | Copy local DSE credentials file to remote server |
| `--node-ssl` | Recursively copy node SSL directory to remote server |
| `--ssl` | Recursively copy SSL directory to remote server |

#### Short Version

    ccm --ssh-host=192.168.33.11 --ssh-username=vagrant --ssh-password=vagrant create test -v 2.0.5 -n 3 -i 192.168.33.1 -s

__Note__: `-i` is used to add an IP prefix during the create process to ensure
          that the nodes communicate using the proper IP address for their node

### Source Distribution

If you'd like to use a source distribution instead of the default binary each time (for example, for Continuous Integration), you can prefix cassandra version with `source:`, for example:

```
ccm create test -v source:2.0.5 -n 3 -s
```

### Automatic Version Fallback

If 'binary:' or 'source:' are not explicitly specified in your version string, then ccm will fallback to building the requested version from git if it cannot access the apache mirrors.

### Git and GitHub

To use the latest version from the [canonical Apache Git repository](https://gitbox.apache.org/repos/asf?p=cassandra.git), use the version name `git:branch-name`, e.g.:

```
ccm create trunk -v git:trunk -n 5
```

and to download a branch from a GitHub fork of Cassandra, you can prefix the repository and branch with `github:`, e.g.:

```
ccm create patched -v github:jbellis/trunk -n 1
```

### Bash command-line completion
ccm has many sub-commands for both cluster commands as well as node commands, and sometimes you don't quite remember the name of the sub-command you want to invoke. Also, command lines may be long due to long cluster or node names.

Leverage bash's *programmable completion* feature to make ccm use more pleasant. Copy `misc/ccm-completion.bash` to somewhere in your home directory (or /etc if you want to make it accessible to all users of your system) and source it in your `.bash_profile`:
```
. ~/scripts/ccm-completion.bash
```

Once set up, `ccm sw<tab>` expands to `ccm switch `, for example. The `switch` sub-command has extra completion logic to help complete the cluster name. So `ccm switch cl<tab>` would expand to `ccm switch cluster-58` if cluster-58 is the only cluster whose name starts with "cl". If there is ambiguity, hitting `<tab>` a second time shows the choices that match:
```
$ ccm switch cl<tab>
    ... becomes ...
$ ccm switch cluster-
    ... then hit tab twice ...
cluster-56  cluster-85  cluster-96
$ ccm switch cluster-8<tab>
    ... becomes ...
$ ccm switch cluster-85
```

It dynamically determines available sub-commands based on the ccm being invoked. Thus, users running multiple ccm's (or a ccm that they are continuously updating with new commands) will automagically work.

The completion script relies on ccm having two hidden subcommands:
* show-cluster-cmds - emits the names of cluster sub-commands.
* show-node-cmds - emits the names of node sub-commands.

Thus, it will not work with sufficiently old versions of ccm.


Remote debugging
-----------------------

If you would like to connect to your Cassandra nodes with a remote debugger you have to pass the `-d` (or `--debug`) flag to the populate command:

    ccm populate -d -n 3

That will populate 3 nodes on IP 127.0.0.[1, 2, 3] setting up the remote debugging on ports 2100, 2200 and 2300.
The main thread will not be suspended so you don't have to connect with a remote debugger to start a node.

Alternatively you can also specify a remote port with the `-r` (or `--remote-debug-port`) flag while adding a node

    ccm add node4 -r 5005 -i 127.0.0.4 -j 7400 -b

Where things are stored
-----------------------

By default, ccm stores all the node data and configuration files under `~/.ccm/cluster_name/`.
This can be overridden using the `--config-dir` option with each command.



Third Party Clusters
====================

`ccmlib.Cluster` and `ccmlib.Node` are designed to be extended for third party cluster types.  DataStax Enterprise (DSE) and Hyper Converged Database (HCD) are example implementations.

DataStax Enterprise (DSE)
-------------------------

CCM 2.0 supports creating and interacting with DSE clusters. The `--dse` option must be used with the `ccm create` command. See the `ccm create -h` help for assistance.


Hyper Converged Database (HCD)
------------------------------

The `--hcd` option must be used with the `ccm create` command. See the `ccm create -h` help for assistance.
