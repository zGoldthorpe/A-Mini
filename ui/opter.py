"""
Opter
=======
Goldthorpe
"""

import re

import utils.printing

from ui.errors import perror, die, unexpected

from ampy.passmanager import (
        BadArgumentException,
        Pass_ID_re,
        )

from opt import OptManager as OM
from opt.tools import Opt, OptList, OptError

class OptUI:

    @classmethod
    def add_arguments(self, parser):
        parser.add_argument("-p", "--add-pass",
                dest="OUIpasses",
                action="append",
                metavar="[PASS | \"PASS(arg0, arg1, ..., k0=v0, k1=v1, ...)\"]",
                help="""Append a pass to run (order-sensitive).
                        All arguments are passed.""")
        parser.add_argument("-l", "--list-passes",
                dest="OUIls",
                action="store_true",
                help="List all available passes and exit.")
        parser.add_argument("-?", "--explain",
                dest="OUIexplain",
                action="store",
                metavar="PASS",
                help="Provide explanation for a particular pass.")
        parser.add_argument("-??", "--explain-full",
                dest="OUIfullyexplain",
                action="store",
                metavar="PASS",
                help="Provide a FULL explaination of a particular pass.")

    @classmethod
    def list_passes(cls):
        """
        Print out the passes
        """
        utils.printing.psubtle("Optimisation passes:")
        spaces = max(len(opt) for opt in OM)
        for opt in sorted(OM):
            utils.printing.pquery(f"\t{opt: <{spaces}}", end=' ')
            utils.printing.phidden(f"({cls._pass_class(opt)})")

    @classmethod
    def fully_explain_pass(cls, passid):
        """
        Print python info about pass
        """
        if passid not in OM:
            die(f"Unrecognised pass {passid}")
        help(OM[passid])

    @classmethod
    def explain_pass(cls, passid):
        """
        Print info about pass
        """
        if passid not in OM:
            die(f"Unrecognised pass {passid}")
        utils.printing.psubtle(passid, end=' ')
        utils.printing.phidden(f"({cls._pass_class(passid)})")
        Pass = OM[passid]
        if Pass.__doc__ is not None:
            utils.printing.pquery(Pass.__doc__)


    @classmethod
    def _pass_class(cls, passid):
        return f"{OM[passid].__module__}.{OM[passid].__name__}"

    @classmethod
    def parse_pass(cls, opt:str):
        """
        Parse pass specified by a string.
        Return a triple (Pass, args, kwargs)
        """
        opt_args = []
        opt_kwargs = {}
        m = re.fullmatch(rf"({Pass_ID_re})\((.*)\)", opt)
        if m is not None:
            opt = m.group(1)
            passed = list(map(lambda s:s.strip(), m.group(2).split(',')))
            for arg in passed:
                if '=' not in arg:
                    opt_args.append(arg)
                else:
                    kw, arg = arg.split('=', 1)
                    opt_kwargs[kw] = arg
        elif re.fullmatch(Pass_ID_re, opt) is None:
            die(f"Invalid pass name {opt}.")

        if opt in OM:
            return OM[opt], opt_args, opt_kwargs

    def __init__(self, parsed_args):
        self._optlist = OptList()

        if parsed_args.OUIls:
            self.list_passes()
            exit()
        if parsed_args.OUIexplain is not None:
            self.explain_pass(parsed_args.OUIexplain)
            exit()
        if parsed_args.OUIfullyexplain is not None:
            self.fully_explain_pass(parsed_args.OUIfullyexplain)
            exit()

        self._passes_ls = parsed_args.OUIpasses

    def load_cfg(self, cfg):
        """
        Load cfg and initialise passes
        """
        self._cfg = cfg
        if self._passes_ls is not None:
            for opt in self._passes_ls:
                self.add_pass(*self.parse_pass(opt))


    def add_pass(self, Pass:type, args:tuple, kwargs:dict):
        """
        Add specified pass constructor to opter.
        Requires a CFG to be loaded
        """
        if not issubclass(Pass, Opt):
            die(f"{Pass.__name__} does not define a subclass of {Opt.__name__}")

        try:
            Pass(self._cfg, self._optlist, *args, **kwargs)
        except BadArgumentException as e:
            die(f"{Pass.ID} received invalid argument.\n{e}")

    def execute_passes(self):
        for opt in self._optlist:
            try:
                opt.perform_opt()
            except OptError as e:
                die(f"{opt.ID} encountered an error in source code.\n\t{repr(e.block[e.index])}\n[{e.block.label}:{e.index}] {e.message}")
            except Exception as e:
                unexpected(e)

    @property
    def CFG(self):
        return self._cfg


