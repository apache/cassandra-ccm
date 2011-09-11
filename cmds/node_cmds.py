import os, sys, shutil, subprocess

L = os.path.realpath(__file__).split(os.path.sep)[:-2]
root = os.path.sep.join(L)
sys.path.append(os.path.join(root, 'ccm_lib'))
from command import Cmd
import common
from node import Node

def node_cmds():
    return [
        "show",
        "remove",
        "showlog",
        "setlog",
        "start",
        "stop",
        "ring",
        "flush",
        "compact",
        "cleanup",
        "repair",
        "scrub",
        "decommission",
        "json",
        "updateconf",
        "stress",
    ]

class NodeShowCmd(Cmd):
    def description(self):
        return "Display information on a node"

    def get_parser(self):
        usage = "usage: ccm node_name show [options]"
        return self._get_default_parser(usage, self.description())

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True, load_cluster=True)

    def run(self):
        self.node.show()

class NodeRemoveCmd(Cmd):
    def description(self):
        return "Remove a node (stopping it if necessary and deleting all its data)"

    def get_parser(self):
        usage = "usage: ccm node_name remove [options]"
        return self._get_default_parser(usage, self.description())

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True, load_cluster=True)

    def run(self):
        del self.cluster.nodes[self.name]
        try:
            self.cluster.seeds.remove(self.node)
        except:
            pass
        self.cluster.save()
        self.node.stop()
        shutil.rmtree(self.node.get_path())

class NodeShowlogCmd(Cmd):
    def description(self):
        return "Show the log of node name (runs your $PAGER on its system.log)"

    def get_parser(self):
        usage = "usage: ccm node_name showlog [options]"
        return self._get_default_parser(usage, self.description())

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True, load_cluster=True)

    def run(self):
        log = os.path.join(self.node.get_path(), 'logs', 'system.log')
        pager = os.environ.get('PAGER', 'less')
        os.execvp(pager, (pager, log))

class NodeSetlogCmd(Cmd):
    def description(self):
        return "Set node name log level (INFO, DEBUG, ...) - require a node restart"

    def get_parser(self):
        usage = "usage: ccm node_name setlog [options] level"
        return self._get_default_parser(usage, self.description())

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True, load_cluster=True)
        self.level = args[1]
        known_level = [ 'TRACE', 'DEBUG', 'INFO', 'ERROR' ]
        if self.level not in known_level:
            print >> sys.stderr, "Unknown log level %s (use one of %s)" % (self.level, " ".join(known_level))
            exit(1)

    def run(self):
        self.node.set_log_level(self.level)

class NodeClearCmd(Cmd):
    def description(self):
        return "Clear the node data & logs (and stop the node nodes)"

    def get_parser(self):
        usage = "usage: ccm node_name_clear [options]"
        parser =  self._get_default_parser(usage, self.description())
        parser.add_option('-a', '--all', action="store_true", dest="all",
                help="Also clear the saved cache and node log files", default=False)
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True, load_cluster=True)

    def run(self):
        self.node.stop()
        self.node.clear(self.options.all)
