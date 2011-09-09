import os, sys, time

L = os.path.realpath(__file__).split(os.path.sep)[:-2]
root = os.path.sep.join(L)
sys.path.append(os.path.join(root, 'ccm_lib'))
from command import Cmd
import common
from node import Node, StartError

class ClusterStartCmd(Cmd):
    def description(self):
        return "Start all the non started nodes of the current cluster"

    def get_parser(self):
        usage = "usage: ccm cluter start [options]"
        parser =  self._get_default_parser(usage, self.description(), cassandra_dir=True)
        parser.add_option('-v', '--verbose', action="store_true", dest="verbose",
            help="Print standard output of cassandra process", default=False)
        parser.add_option('--no-wait', action="store_true", dest="no_wait",
            help="Do not wait for cassandra node to be ready", default=False)
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, load_cluster=True)

    def run(self):
        started = self.cluster.start(self.options.cassandra_dir)

        if self.options.no_wait:
            time.sleep(2) # waiting 2 seconds to check for early errors and
                          # for the pid to be set
        else:
            for node, p in started:
                for line in p.stdout:
                    if self.options.verbose:
                        print "[%s] %s" % (node.name, line.rstrip('\n'))
                if self.options.verbose:
                    print "----"

        self.cluster.update_pids(started)

        for node, p in started:
            if not node.is_running():
                print >> sys.stderr, "Error starting {0}.".format(node.name)
                for line in p.stderr:
                    print >> sys.stderr, line.rstrip('\n')

class ClusterStopCmd(Cmd):
    def description(self):
        return "Stop all the nodes of the cluster"

    def get_parser(self):
        usage = "usage: ccm cluster stop [options] name"
        parser = self._get_default_parser(usage, self.description())
        parser.add_option('-v', '--verbose', action="store_true", dest="verbose",
                help="Print nodes that were not running", default=False)
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, load_cluster=True)

    def run(self):
        not_running = self.cluster.stop()
        if self.options.verbose and len(not_running) > 0:
            sys.out.write("The following nodes were not running: ")
            for node in not_running:
                sys.out.write(node.name + " ")
            print ""

class _ClusterNodetoolCmd(Cmd):
    def get_parser(self):
        parser = self._get_default_parser(self.usage, self.description(), cassandra_dir=True)
        return parser

    def description(self):
        return self.descr_text

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, load_cluster=True)

    def run(self):
        self.cluster.nodetool(self.options.cassandra_dir, self.nodetool_cmd)

class ClusterFlushCmd(_ClusterNodetoolCmd):
    usage = "usage: ccm cluster flush [options] name"
    nodetool_cmd = 'flush'
    descr_text = "Flush all (running) nodes of the cluster"

class ClusterCompactCmd(_ClusterNodetoolCmd):
    usage = "usage: ccm cluster compact [options] name"
    nodetool_cmd = 'compact'
    descr_text = "Compact all (running) node of the cluster"

class ClusterStressCmd(Cmd):
    def description(self):
        return "Run stress using all live nodes"

    def get_parser(self):
        usage = "usage: ccm stress [options] [stress_options]"
        parser = self._get_default_parser(usage, self.description(), cassandra_dir=True, ignore_unknown_options=True)
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, load_cluster=True)
        self.stress_options = parser.get_ignored() + args

    def run(self):
        try:
            self.cluster.stress(self.options.cassandra_dir, self.stress_options)
        except Exception as e:
            print >> sys.stderr, e

class ClusterUpdateconfCmd(Cmd):
    def description(self):
        return "Update the cassandra config files for all nodes"

    def get_parser(self):
        usage = "usage: ccm updateconf [options]"
        parser = self._get_default_parser(usage, self.description(), cassandra_dir=True)
        parser.add_option('--no-hh', '--no-hinted-handoff', action="store_false",
            dest="hinted_handoff", default=True, help="Disable hinted handoff")
        parser.add_option('--batch-cl', '--batch-commit-log', action="store_true",
            dest="cl_batch", default=True, help="Set commit log to batch mode")
        parser.add_option('--rt', '--rpc-timeout', action="store", type='int',
            dest="rpc_timeout", help="Set rpc timeout")
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, load_cluster=True)

    def run(self):
        self.cluster.set_configuration_option("hinted_handoff_enabled", self.options.hinted_handoff)
        if self.options.rpc_timeout:
            self.cluster.set_configuration_option("rpc_timeout_in_ms", self.options.rpc_timeout)
        if self.options.cl_batch:
            self.cluster.set_configuration_option("commitlog_sync", "batch")
            self.cluster.set_configuration_option("commitlog_sync_batch_window_in_ms", 5)
            self.cluster.unset_configuration_option("commitlog_sync_period_in_ms")
        self.cluster.update_configuration(self.options.cassandra_dir)
