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
from ui.stats       import StatUI
from ui.testfiles   import TestFileUI
from ui.opter       import OptUI
from ui.writer      import WriterUI

import ui.stats

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
                tfmanager.get_test_opt(test, opt),
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

def run_code_stats(tfmanager, multi, stats):
    
    print("Code report")
    print()
    print("Stats:")
    print("I:   number of instructions in the code")
    print("B:   number of basic blocks in the code")
    print("V:   number of distinct registers")
    print("phi: number of phi nodes")
    print()

    # collect optimisations and stats
    
    code_stats = {}
    def save_code_stats(src):
        reader = ReaderUI(src)
        reader.fetch_input()
        cfg = reader.build_cfg()
        code_stats[src] = ui.stats.get_cfg_stats(cfg)

    optset = set()
    for test in tfmanager.tests:
        save_code_stats(tfmanager.get_test_ami(test))
        for opt in tfmanager.get_test_opts(test):
            optset.add(opt)
            save_code_stats(tfmanager.get_test_opt(test, opt))

    nickname = ui.stats.name_compressor(optset)

    nlen = max(len(nick) for opt, nick in nickname.items())
    print("Optimisations:")
    for opt, nick in sorted(nickname.items(), key=lambda t: t[1]):
        print(f"{nick: >{nlen}}", "->", opt)
    print()
    print('='*max(len(test) for test in tfmanager.tests))
    print()

    # now, build report

    for test in tfmanager.tests:
        print(test, '-'*len(test), sep='\n')
        ref = "-"

        subjects = { ref : tfmanager.get_test_ami(test) }
        for opt in tfmanager.get_test_opts(test):
            subjects[nickname[opt]] = tfmanager.get_test_opt(test, opt)

        stats.print_stats(header="stat", subjects=subjects,
                params=[
                    ("I", lambda src: code_stats[src]["num_instructions"]),
                    ("B", lambda src: code_stats[src]["num_blocks"]),
                    ("V", lambda src: code_stats[src]["num_vars"]),
                    ("phi", lambda src: code_stats[src]["num_phi"])],
                ref=ref,
                flip=True # the smaller, the better
                )
        print()

def run_trace_stats(tfmanager, multi, stats):
    
    print("Trace report")
    print()
    print("Stats: (per test input)")
    print("I:   number of instructions executed")
    print("BB:  number of basic blocks visited")
    print("br:  number of conditional branches")
    print()

    # collect optimisations and stats
    
    trace_stats = {}
    def save_trace_stats(src):
        try:
            with open(src) as file:
                trace_stats[src] = ui.stats.get_trace_stats(file.read())
            return True
        except FileNotFoundError:
            utils.debug.print("run_trace", f"{src} does not exist.")
            return False


    optset = set()
    for test in tfmanager.tests:
        for opt in tfmanager.get_test_opts(test):
            optset.add(opt)
            for inf in tfmanager.get_test_input_files(test):
                save_trace_stats(
                        tfmanager.get_test_corresponding_trace_fpath(test, inf))
                
                save_trace_stats(
                        tfmanager.get_test_opt_corresponding_trace_fpath(test, opt, inf))

    nickname = ui.stats.name_compressor(optset)

    nlen = max(len(nick) for opt, nick in nickname.items())
    print("Optimisations:")
    for opt, nick in sorted(nickname.items(), key=lambda t: t[1]):
        print(f"{nick: >{nlen}}", "->", opt)
    print()
    print('='*max(len(test) for test in tfmanager.tests))
    print()

    # now, build report

    for test in tfmanager.tests:
        if any(tfmanager.get_test_corresponding_trace_fpath(
                test, inf) not in trace_stats
                for inf in tfmanager.get_test_input_files(test)):
            continue
        print(test, '-'*len(test), sep='\n')
        ref = "-"

        subjects = { ref : None }
        for opt in tfmanager.get_test_opts(test):
            if any(tfmanager.get_test_opt_corresponding_trace_fpath(
                    test, opt, inf) not in trace_stats
                    for inf in tfmanager.get_test_input_files(test)):
                continue
            subjects[nickname[opt]] = opt

        stats.print_stats(header="input", subjects=subjects,
                params=sum(([
                    (f"{inf}/I", lambda opt: trace_stats[
                        tfmanager.get_test_opt_corresponding_trace_fpath(
                            test, opt, inf)
                        if opt is not None else
                        tfmanager.get_test_corresponding_trace_fpath(
                            test, inf)]["num_instructions"]),
                    (f"{inf}/BB", lambda opt: trace_stats[
                        tfmanager.get_test_opt_corresponding_trace_fpath(
                            test, opt, inf)
                        if opt is not None else
                        tfmanager.get_test_corresponding_trace_fpath(
                            test, inf)]["num_blocks"]),
                    (f"{inf}/br", lambda opt: trace_stats[
                        tfmanager.get_test_opt_corresponding_trace_fpath(
                            test, opt, inf)
                        if opt is not None else
                        tfmanager.get_test_corresponding_trace_fpath(
                            test, inf)]["num_branches"]),
                        ] for inf in sorted(tfmanager.get_test_input_files(test))),
                        start=[]),
                ref=ref,
                flip=True # the smaller, the better
                )
        print()


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

    ### stats arguments ###
    stats_parser = subparsers.add_parser("stats",
                    description="Test statistics.",
                    help="Get statistics report for specified subtree(s).")
    StatUI.add_arguments(stats_parser)
    stats_parser.add_argument("stat",
                    choices=("code", "trace"),
                    help="Specify which statistics to report on.")

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

        case "stats":
            stats = StatUI.arg_init(args)
            if args.stat == "code":
                run_code_stats(tfmanager, multi, stats)
            else:
                run_trace_stats(tfmanager, multi, stats)
