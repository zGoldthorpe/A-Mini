"""
Batch testing
===============
Goldthorpe

This module will perform all of the testing and analysis for
optimisation passes.
"""

import argparse
import multiprocessing

from ui.multi     import MultiUI
from ui.printer   import PrinterUI
from ui.reader    import ReaderUI
from ui.testfiles import TestFileUI
from ui.opter     import OptUI
from ui.writer    import WriterUI

def batch_opt(tfmanager, multi, opter, *, meta=True):
    """
    This function is responsible for generating the optimised code files.
    """
    opt = ''.join(','.join(opter.opts_cl).split())
    
    # target process function
    def run_opt(test):
        ns = argparse.Namespace()
        # simulate inline arguments
        # reader
        ns.fname = tfmanager.get_test_ami(test)
        # printer
        ns.PUIformat = False
        ns.PUIdebug = True
        # writer
        ns.WUImeta = meta
        ns.WUIframe = None
        ns.WUIoutput = tfmanager.get_test_corresponding_opt(test, opt)

        PrinterUI(ns)
        reader = ReaderUI(ns)
        writer = WriterUI(ns)
        
        # parse
        reader.fetch_input()
        cfg = reader.build_cfg()

        # optimise
        opter.load_cfg(cfg)
        opter.execute_passes()

        # write
        writer.write(opter.CFG)

    # set up processes
    for test in tfmanager.tests:
        if opt in tfmanager.get_test_opts(test):
            continue
        multi.prepare_process(
                tfmanager.get_test_corresponding_opt(test, opt),
                target=run_opt,
                args=(test,),
                stderr=tfmanager.get_test_opt_corresponding_log(test, opt))

    res_dict = multi.execute()


if __name__ == "__main__":

    ### command-line argument handling ###

    argparser = argparse.ArgumentParser(
                    description="All-purpose optimisation tester and analyser.")

    PrinterUI.add_arguments(argparser.add_argument_group("formatting"))
    MultiUI.add_arguments(argparser.add_argument_group("multiprocessing"))
    TestFileUI.add_arguments(argparser.add_argument_group("file management"))

    subparsers = argparser.add_subparsers(title="test types", dest="type")
    opt_parser = subparsers.add_parser("opt",
                    description="Run optimisation passes through code suite.",
                    help="Pass optimisations.")
    OptUI.add_arguments(opt_parser)
    opt_parser.add_argument("-M", "--omit-metadata",
                    dest="meta",
                    action="store_false",
                    help="Do not write metadata to optimised output code.")

    args = argparser.parse_args()
    PrinterUI(args)

    multi = MultiUI(args)
    tfmanager = TestFileUI(args)

    tfmanager.verify_folder_integrity()

    if args.type == "opt":
        opter = OptUI(args)
        tfmanager.delete_outdated()

        batch_opt(tfmanager, multi, opter, meta=args.meta)
