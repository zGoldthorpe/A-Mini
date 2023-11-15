"""
Batch testing
===============
Goldthorpe

This module will perform all of the testing and analysis for
optimisation passes.
"""

import argparse
import multiprocessing

from ui.diff        import DiffUI
from ui.interpreter import InterpreterUI
from ui.multi       import MultiUI
from ui.printer     import PrinterUI
from ui.reader      import ReaderUI
from ui.testfiles   import TestFileUI
from ui.opter       import OptUI
from ui.writer      import WriterUI

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
        ns.WUIoutput = tfmanager.get_test_opt(test, opt)

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
                "OPT :: " + tfmanager.get_test_opt(test, opt),
                target=run_opt,
                args=(test,),
                stderr=tfmanager.get_test_opt_log(test, opt))

    return multi.execute()

def batch_run(tfmanager, multi):
    """
    This function is responsible for generating the necessary output files.
    """

    # target process function
    def simulate(fname):
        ns = argparse.Namespace()
        # simulate inline arguments
        # reader
        ns.fname = fname
        # printer
        ns.PUIformat = False
        ns.PUIdebug = True
        # interpreter
        ns.IUIprompt = False
        ns.IUItrace = True
        ns.IUIbrkpts = False
        ns.IUIinterrupt = "never"
        

        PrinterUI(ns)
        reader = ReaderUI(ns)
        interpreter = InterpreterUI(ns)
        
        # parse
        reader.fetch_input()
        cfg = reader.build_cfg()

        # run
        interpreter.load_cfg(cfg)
        interpreter.run()

    # set up processes
    for test in tfmanager.tests:
        for inf in tfmanager.get_test_input_files(test):
            outf = tfmanager.get_test_corresponding_output(test, inf)

            if outf not in tfmanager.get_test_output_files(test):
                multi.prepare_process(
                        tfmanager.get_test_output_fpath(test, outf),
                        target=simulate,
                        args=(tfmanager.get_test_ami(test),),
                        stdin=tfmanager.get_test_input_fpath(test, inf),
                        stdout=tfmanager.get_test_output_fpath(test, outf),
                        stderr=tfmanager.get_test_corresponding_trace_fpath(test, inf))

            for opt in tfmanager.get_test_opts(test):
                if outf not in tfmanager.get_test_opt_output_files(test, opt):
                    multi.prepare_process(
                            tfmanager.get_test_opt_output_fpath(test, opt, outf),
                            target=simulate,
                            args=(tfmanager.get_test_opt(test, opt),),
                            stdin=tfmanager.get_test_input_fpath(test, inf),
                            stdout=tfmanager.get_test_opt_output_fpath(test, opt, outf),
                            stderr=tfmanager.get_test_opt_corresponding_trace_fpath(test, opt, inf))

    return multi.execute()

def batch_diff(tfmanager, multi):
    """
    Compare optimised outputs with original for inconsistencies.
    """
    # target process function
    def run_diff(file1, file2):
        ns = argparse.Namespace()
        ns.PUIformat = False
        ns.PUIdebug = False
        ns.DUIwidth = 48
        ns.DUIall = True
        PrinterUI(ns)
        diff = DiffUI(ns)

        diff.read_files(file1, file2)
        diff.display_diff()

        exit(diff.files_differ)


    # set up processes
    for test in tfmanager.tests:
        for opt in tfmanager.get_test_opts(test):
            for outf in tfmanager.get_test_output_files(test):
                multi.prepare_process(
                        tfmanager.get_test_opt_corresponding_diff_fpath(test, opt, outf),
                        target=run_diff,
                        args=(tfmanager.get_test_output_fpath(test, outf),
                                tfmanager.get_test_opt_output_fpath(test, opt, outf)),
                        stdout=tfmanager.get_test_opt_corresponding_diff_fpath(test, opt, outf))

    return multi.execute()



if __name__ == "__main__":

    ### command-line argument handling ###

    argparser = argparse.ArgumentParser(
                    description="All-purpose optimisation tester and analyser.")

    PrinterUI.add_arguments(argparser.add_argument_group("formatting"))
    MultiUI.add_arguments(argparser.add_argument_group("multiprocessing"))
    TestFileUI.add_arguments(argparser.add_argument_group("file management"))

    subparsers = argparser.add_subparsers(title="test types", dest="type")
    opt_parser = subparsers.add_parser("opt",
                    description="Apply optimisation passes to code suite.",
                    help="Pass optimisations.")
    OptUI.add_arguments(opt_parser)
    opt_parser.add_argument("-M", "--omit-metadata",
                    dest="meta",
                    action="store_false",
                    help="Do not write metadata to optimised output code.")

    run_parser = subparsers.add_parser("run",
                    description="Generate output for corresponding inputs.",
                    help="Run code with provided inputs.")

    diff_parser = subparsers.add_parser("diff",
                    description="Produce diff between two files.",
                    help="Diff two files.")
    diff_parser.add_argument("file1",
                    metavar="FILE",
                    help="First file of diff.")
    diff_parser.add_argument("file2",
                    metavar="FILE",
                    help="Second file of diff.")
    DiffUI.add_arguments(diff_parser)



    args = argparser.parse_args()
    PrinterUI(args)

    multi = MultiUI(args)
    tfmanager = TestFileUI(args)

    tfmanager.verify_folder_integrity()
    tfmanager.delete_outdated()

    match args.type:

        case "opt":
            opter = OptUI(args)
            res = batch_opt(tfmanager, multi, opter, meta=args.meta)
            if any(ec for _, ec in res.items()):
                exit(99)

        case "run":
            res = batch_run(tfmanager, multi)
            if any(ec for _, ec in res.items()):
                exit(99)
            
            tfmanager.rescan() # process newly-created files
            dres = batch_diff(tfmanager, multi)
            if any(ec for _, ec in dres.items()):
                exit(99)

        case "diff":
            diff = DiffUI(args)
            diff.read_files(args.file1, args.file2)
            diff.display_diff()
            exit(diff.files_differ)
            
