"""
Batch testing
===============
Goldthorpe

This module will perform all of the testing and analysis for
optimisation passes.
"""

import argparse
import multiprocessing

import utils.printing

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
        PrinterUI(can_format=False, debug=True)
        reader = ReaderUI(fname=tfmanager.get_test_ami(test))
        writer = WriterUI(meta=meta, frame=None,
                fname=tfmanager.get_test_opt(test, opt))
        
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
        PrinterUI(can_format=False, debug=True)
        reader = ReaderUI(fname=fname)
        interpreter = InterpreterUI(prompt=False,
                                trace=True,
                                brkpts=False,
                                interrupt="never")
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
        PrinterUI(can_format=False, debug=False)
        diff = DiffUI(fullcontent=True)

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

    ### opt arguments ###
    opt_parser = subparsers.add_parser("opt",
                    description="Apply optimisation passes to code suite.",
                    help="Pass optimisations.")
    OptUI.add_arguments(opt_parser)
    opt_parser.add_argument("-M", "--omit-metadata",
                    dest="meta",
                    action="store_false",
                    help="Do not write metadata to optimised output code.")
    
    ### run arguments ###
    run_parser = subparsers.add_parser("run",
                    description="Generate output for corresponding inputs.",
                    help="Run code with provided inputs.")

    ### diff arguments ###
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
    PrinterUI.arg_init(args)

    multi = MultiUI.arg_init(args)
    tfmanager = TestFileUI.arg_init(args)

    tfmanager.verify_folder_integrity()
    tfmanager.delete_outdated()

    match args.type:

        case "opt":
            utils.printing.phidden("batch_opt :: updating optimised files")
            opter = OptUI.arg_init(args)
            res = batch_opt(tfmanager, multi, opter, meta=args.meta)
            if any(ec for _, ec in res.items()):
                exit(99)

        case "run":
            utils.printing.phidden("batch_run :: updating output files")
            res = batch_run(tfmanager, multi)
            if any(ec for _, ec in res.items()):
                exit(99)
            
            utils.printing.phidden("batch_diff :: checking output file correctnesss")
            tfmanager.rescan() # process newly-created files
            dres = batch_diff(tfmanager, multi)
            if any(ec for _, ec in dres.items()):
                exit(99)

        case "diff":
            diff = DiffUI.arg_init(args)
            diff.read_files(args.file1, args.file2)
            diff.display_diff()
            exit(diff.files_differ)
            
