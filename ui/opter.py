"""
Opter
=======
Goldthorpe
"""

import re
import time

import utils.debug
import utils.printing

from ui.errors import perror, die, unexpected

from ampy.passmanager import (
        BadArgumentException,
        Pass_ID_re,
        )
import ampy.types

from opt import OptManager as OM
from opt.tools import Opt, OptList, OptError

class OptUI:

    @classmethod
    def add_arguments(cls, parser):
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
        for opt in sorted(OM, key=lambda opt: cls._pass_class(opt)):
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
        Pass = OM[passid]
        utils.printing.psubtle(Pass.ID, end=' ')
        if Pass.generic_defs != Pass.ID:
            utils.printing.psubtle("=", Pass.generic_defs, end=' ')
        utils.printing.phidden(f"({cls._pass_class(passid)})\n")
        utils.printing.pquery(Pass.generic)
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
        m = re.fullmatch(fr"({Pass_ID_re})\((.*)\)", opt)
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
        die(f"Cannot recognise pass {opt}.")
    
    @classmethod
    def parse_pipeline(cls, opts:str):
        """
        Parse a list of multiple passes and return the list of (Pass, args, kwargs) triples.
        """
        return [cls.parse_pass(opt) for opt in re.findall(
            fr"{Pass_ID_re}(?:\([^()]*\)|(?=\s*(?:[^()]|$)))", opts)]

    @classmethod
    def arg_init(cls, parsed_args):
        return cls(ls=parsed_args.OUIls,
                explain=parsed_args.OUIexplain,
                fullyexplain=parsed_args.OUIfullyexplain,
                passes_ls=parsed_args.OUIpasses)

    def __init__(self, ls=False, explain=None, fullyexplain=None, passes_ls=[]):
        self._optlist = OptList()

        if ls:
            self.list_passes()
            exit()
        if explain is not None:
            self.explain_pass(explain)
            exit()
        if fullyexplain is not None:
            self.fully_explain_pass(fullyexplain)
            exit()

        if passes_ls is None:
            passes_ls = ()
        self._passes_ls = [self.parse_pass(opt) for opt in passes_ls]

    def load_cfg(self, cfg):
        """
        Load cfg and initialise passes
        """
        self._cfg = cfg
        if self._passes_ls is not None:
            for opt, args, kwargs in self._passes_ls:
                self.add_pass(opt, args, kwargs)

    def append_pass(self, Pass:type, args:tuple, kwargs:dict):
        """
        Append specified pass constructor to opter.
        Do this *prior* to loading the CFG
        """
        self._passes_ls.append((Pass, args, kwargs))

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
        start_time = time.process_time()
        for opt in list(self._optlist):
            # copy list in case opt calls append new opts
            try:
                opt.perform_opt()
            except OptError as e:
                die(f"{opt.ID} encountered an error in source code.\n\t{repr(e.block[e.index])}\n[{e.block.label}:{e.index}] {e.message}")
            except Exception as e:
                unexpected(e)
        delta = time.process_time() - start_time
        utils.debug.print("opt", f"completed in {delta:.3f}s")

    @property
    def opts_cl(self):
        """
        Tuple of passes as given from the command line.
        """
        # this is a little hacky to trick opt to initialise with
        # an empty CFG and an empty 
        return tuple(opt(ampy.types.CFG(), OptList(), *args, **kwargs).name for opt, args, kwargs in self._passes_ls)


    @property
    def CFG(self):
        return self._cfg


