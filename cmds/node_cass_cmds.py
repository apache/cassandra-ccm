import os, sys, time

L = os.path.realpath(__file__).split(os.path.sep)[:-2]
root = os.path.sep.join(L)
sys.path.append(os.path.join(root, 'ccm_lib'))
from command import Cmd
import common
from node import Node, StartError, ArgumentError

class NodeStartCmd(Cmd):
    def description(self):
        return "Start a node"

    def get_parser(self):
        usage = "usage: ccm node start [options] name"
        parser = self._get_default_parser(usage, self.description(), cassandra_dir=True)
        parser.add_option('-v', '--verbose', action="store_true", dest="verbose",
            help="Print standard output of cassandra process", default=False)
        parser.add_option('--no-wait', action="store_true", dest="no_wait",
            help="Do not wait for cassandra node to be ready", default=False)
        parser.add_option('-j', '--dont-join-ring', action="store_true", dest="no_join_ring",
            help="Launch the instance without joining the ring", default=False)
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True, load_cluster=True)

    def run(self):
        if self.node.is_running():
            print >> sys.stderr, "%s is already running" % self.name
            exit(1)

        try:
            process = self.node.start(self.options.cassandra_dir, not self.options.no_join_ring)
        except StartError as e:
            print >> sys.stderr, str(e)
            print >> sys.stderr, "Standard error output is:"
            for line in e.process.stderr:
                print >> sys.stderr, line.rstrip('\n')
            exit(1)

        if self.options.no_wait:
            time.sleep(2) # waiting 2 seconds to check for early errors and
                          # for the pid to be set
        else:
            for line in process.stdout:
                if self.options.verbose:
                    print line.rstrip('\n')

        self.node.update_pid(process)

        if not self.node.is_running():
            print >> sys.stderr, "Error starting node."
            for line in process.stderr:
                print >> sys.stderr, line.rstrip('\n')

class NodeStopCmd(Cmd):
    def description(self):
        return "Stop a node"

    def get_parser(self):
        usage = "usage: ccm node stop [options] name"
        parser = self._get_default_parser(usage, self.description())
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True, load_cluster=True)

    def run(self):
        if not self.node.stop():
            print >> sys.stderr, "%s is not running" % self.name
            exit(1)

class _NodeToolCmd(Cmd):
    def get_parser(self):
        parser = self._get_default_parser(self.usage, self.description(), cassandra_dir=True)
        return parser

    def description(self):
        return self.descr_text

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True, load_cluster=True)

    def run(self):
        self.node.nodetool(self.options.cassandra_dir, self.nodetool_cmd)

class NodeRingCmd(_NodeToolCmd):
    usage = "usage: ccm node_name ring [options]"
    nodetool_cmd = 'ring'
    descr_text = "Print ring (connecting to node name)"

class NodeFlushCmd(_NodeToolCmd):
    usage = "usage: ccm node_name flush [options]"
    nodetool_cmd = 'flush'
    descr_text = "Flush node name"

class NodeCompactCmd(_NodeToolCmd):
    usage = "usage: ccm node_name compact [options]"
    nodetool_cmd = 'compact'
    descr_text = "Compact node name"

class NodeCleanupCmd(_NodeToolCmd):
    usage = "usage: ccm node_name cleanup [options]"
    nodetool_cmd = 'cleanup'
    descr_text = "Run cleanup on node name"

class NodeRepairCmd(_NodeToolCmd):
    usage = "usage: ccm node_name repair [options]"
    nodetool_cmd = 'repair'
    descr_text = "Run repair on node name"

class NodeDecommissionCmd(_NodeToolCmd):
    usage = "usage: ccm node_name decommission [options]"
    nodetool_cmd = 'decommission'
    descr_text = "Run decommission on node name"

    def run(self):
        _NodeToolCmd.run(self)
        self.node.decommission()

class NodeScrubCmd(_NodeToolCmd):
    usage = "usage: ccm node_name scrub [options]"
    nodetool_cmd = 'scrub'
    descr_text = "Run scrub on node name"

class NodeCliCmd(Cmd):
    def description(self):
        return "Launch a cassandra cli connected to this node"

    def get_parser(self):
        usage = "usage: ccm node_name cli [options]"
        parser = self._get_default_parser(usage, self.description(), cassandra_dir=True)
        parser.add_option('-x', '--exec', type="string", dest="cmds", default=None,
            help="Execute the specified commands and exit")
        parser.add_option('-v', '--verbose', action="store_true", dest="verbose",
            help="With --exec, show cli output after completion", default=False)
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True, load_cluster=True)

    def run(self):
        self.node.run_cli(self.options.cassandra_dir, self.options.cmds, self.options.verbose)

class NodeJsonCmd(Cmd):
    def description(self):
        return "Call sstable2json on the sstables of this node"

    def get_parser(self):
        usage = "usage: ccm node_name json [options] [file]"
        parser = self._get_default_parser(usage, self.description(), cassandra_dir=True)
        parser.add_option('-k', '--keyspace', type="string", dest="keyspace",
            help="The keyspace to use [use all keyspaces by default]")
        parser.add_option('-c', '--column-families', type="string", dest="cfs",
            help="Comma separated list of column families to use (requires -k to be set)")
        parser.add_option('-e', '--enumerate-keys', action="store_true", dest="enumerate_keys",
            help="Only enumerate keys (i.e, call sstable2keys)", default=False)
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True, load_cluster=True)
        self.keyspace = options.keyspace
        self.column_families = None
        if len(args) > 0:
            self.datafile = args[0]
            if not self.keyspace:
                print >> sys.stderr, "You need a keyspace specified (option -k) if you specify a file"
                exit(1)
        elif options.cfs:
            self.datafile = None
            if not self.keyspace:
                print >> sys.stderr, "You need a keyspace specified (option -k) if you specify column families"
                exit(1)
            self.column_families = options.cfs.split(',')

    def run(self):
        try:
            self.node.run_sstable2json(self.options.cassandra_dir, self.keyspace, self.datafile, self.column_families, self.options.enumerate_keys)
        except ArgumentError as e:
            print >> sys.stderr, e

class NodeUpdateconfCmd(Cmd):
    def description(self):
        return "Update the cassandra config files for this node (useful when updating cassandra)"

    def get_parser(self):
        usage = "usage: ccm node_name updateconf [options]"
        parser = self._get_default_parser(usage, self.description(), cassandra_dir=True)
        parser.add_option('--no-hh', '--no-hinted-handoff', action="store_false",
            dest="hinted_handoff", default=True, help="Disable hinted handoff")
        parser.add_option('--batch-cl', '--batch-commit-log', action="store_true",
            dest="cl_batch", default=False, help="Set commit log to batch mode")
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True, load_cluster=True)

    def run(self):
        self.node.set_configuration_option("hinted_handoff_enabled", self.options.hinted_handoff)
        if self.options.cl_batch:
            self.node.set_configuration_option("commitlog_sync", "batch")
            self.node.set_configuration_option("commitlog_sync_batch_window_in_ms", 5)
            self.node.unset_configuration_option("commitlog_sync_period_in_ms")
        self.node.update_configuration(self.options.cassandra_dir)

class NodeStressCmd(Cmd):
    def description(self):
        return "Run stress on a node"

    def get_parser(self):
        usage = "usage: ccm node_name stress [options] [stress_options]"
        parser = self._get_default_parser(usage, self.description(), cassandra_dir=True, ignore_unknown_options=True)
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True, load_cluster=True)
        self.stress_options = parser.get_ignored() + args[1:]

    def run(self):
        try:
            self.node.stress(self.options.cassandra_dir, self.stress_options)
        except OSError:
            print >> sys.stderr, "Could not find stress binary (you may need to build it)"
