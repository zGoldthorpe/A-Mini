"""
Batch testing
===============
Goldthorpe

This module will perform all of the testing and analysis for
optimisation passes.
"""

import argparse
import multiprocessing
import os

import utils.printing

from ui.diff        import DiffUI
from ui.fuzz        import FuzzUI
from ui.interpreter import InterpreterUI
from ui.multi       import MultiUI
from ui.printer     import PrinterUI
from ui.reader      import ReaderUI
from ui.stats       import StatUI
from ui.testfiles   import TestFileUI
from ui.opter       import OptUI
from ui.writer      import WriterUI

import ui.fuzz
import ui.stats

def batch_opt(tfmanager, multi, opter, *, meta=True, fresh=False):
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
        if opt in tfmanager.get_test_opts(test) and not fresh:
            continue
        multi.prepare_process(
                tfmanager.get_test_opt(test, opt),
                target=run_opt,
                args=(test,),
                stderr=tfmanager.get_test_opt_log(test, opt))

    return multi.execute()

def batch_fuzz_ami(tfmanager, multi, fuzz, *, num):
    """
    This function is responsible for generating ami source fuzz.
    """
    def build_fuzz(fname):
        PrinterUI(can_format=False, debug=False)
        writer = WriterUI(meta=False, frame=None,
                fname=fname)
        writer.write(fuzz.generate())
        
    for _ in range(num):
        fname = tfmanager.new_fuzz_ami()
        multi.prepare_process(
                fname,
                target=build_fuzz,
                args=(fname,))

    return multi.execute()

def batch_fuzz_input(tfmanager, multi, *, num, intmin, intmax):
    """
    This function is responsible for generating input fuzz.
    Also produces the corresponding trace for the input.
    """
    def say_and_write(fname):
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

    for test in tfmanager.tests:

        for _ in range(num):
            inf = tfmanager.new_fuzz_input(test)
            outf = tfmanager.get_test_corresponding_output(test, inf)
            infile = tfmanager.get_test_input_fpath(test, inf)

            multi.prepare_process(
                    tfmanager.get_test_output_fpath(test, outf),
                    target=say_and_write,
                    args=(tfmanager.get_test_ami(test),),
                    stdin=ui.fuzz.FuzzWriter(infile, intmin, intmax),
                    stdout=tfmanager.get_test_output_fpath(test, outf),
                    stderr=tfmanager.get_test_corresponding_trace_fpath(test, inf))

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
                diff = tfmanager.get_test_opt_corresponding_diff_fpath(test, opt, outf)
                if os.path.exists(diff):
                    continue
                multi.prepare_process(
                        diff,
                        target=run_diff,
                        args=(tfmanager.get_test_output_fpath(test, outf),
                                tfmanager.get_test_opt_output_fpath(test, opt, outf)),
                        stdout=tfmanager.get_test_opt_corresponding_diff_fpath(test, opt, outf))

    return multi.execute()

def run_code_stats(tfmanager, multi, stats, *, ref):
    
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

    if ref != '-':
        if ref in nickname:
            ref = nickname[ref]
        elif ref not in nickname.values():
            utils.printing.perror(f"{ref} is not a valid baseline.")
            utils.printing.perror("The valid baselines are:\n\t-")
            for opt, nick in nickname.items():
                utils.printing.perror(f"\t{opt} or \"{nick}\"")
            exit(1)

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

        subjects = { ref : tfmanager.get_test_ami(test) }
        for opt in tfmanager.get_test_opts(test):
            subjects[nickname[opt]] = tfmanager.get_test_opt(test, opt)

        paramlist = (
                ("I", "num_instructions"),
                ("B", "num_blocks"),
                ("V", "num_vars"),
                ("phi", "num_phi"))
        data = {key:{} for key, _ in paramlist}
        if ref == '-':
            for key, param in paramlist:
                data[key][ref] = code_stats[tfmanager.get_test_ami(test)][param]
        for opt in tfmanager.get_test_opts(test):
            for key, param in paramlist:
                data[key][nickname[opt]] = code_stats[
                        tfmanager.get_test_opt(test, opt)][param]
        stats.print_data(header="stat", data=data,
                paramlist=[key for key, _ in paramlist],
                ref=ref,
                flip=True # the smaller, the better
                )
        print()

def run_trace_stats(tfmanager, multi, stats, *, ref):
    
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

    if ref != '-':
        if ref in nickname:
            ref = nickname[ref]
        elif ref not in nickname.values():
            utils.printing.perror(f"{ref} is not a valid baseline.")
            utils.printing.perror("The valid baselines are:\n\t-")
            for opt, nick in nickname.items():
                utils.printing.perror(f"\t{opt} or \"{nick}\"")
            exit(1)

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
        paramlist = sum(([
                (f"{inf}/I", inf, "num_instructions"),
                (f"{inf}/BB", inf, "num_blocks"),
                (f"{inf}/br", inf, "num_branches")
                ] for inf in tfmanager.get_test_input_files(test)),
                start=[])

        data = {key:{} for key, _, _ in paramlist}
        if ref == "-":
            for key, inf, param in paramlist:
                data[key][ref] = trace_stats[
                        tfmanager.get_test_corresponding_trace_fpath(
                            test, inf)][param]
        for opt in tfmanager.get_test_opts(test):
            if any(tfmanager.get_test_opt_corresponding_trace_fpath(
                    test, opt, inf) not in trace_stats
                    for inf in tfmanager.get_test_input_files(test)):
                continue
            for key, inf, param in paramlist:
                data[key][nickname[opt]] = trace_stats[
                        tfmanager.get_test_opt_corresponding_trace_fpath(
                            test, opt, inf)][param]

        stats.print_data(header="input", data=data,
                paramlist=[key for key, _, _ in paramlist],
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
    opt_parser.add_argument("-f", "--file",
                    dest="opt_file",
                    metavar="FILE",
                    help="Run each program through several optimisation pipelines, where each pipeline is given by a line of space-separated passes in the specified file.")
    opt_parser.add_argument("-m", "--keep-metadata",
                    dest="meta",
                    action="store_true",
                    help="Write metadata to optimised output code.")
    opt_parser.add_argument("--fresh",
                    dest="fresh_opt",
                    action="store_true",
                    help="Do a clean rebuild, and overwrite already existing files for this optimisation.")

    ### fuzz arguments ###
    fuzz_parser = subparsers.add_parser("fuzz",
                    description="A-Mi fuzzer",
                    help="Generate more code or inputs.")
    fuzz_sub = fuzz_parser.add_subparsers(title="fuzz types", dest="fuzz_type")
    fuzz_ami = fuzz_sub.add_parser("ami",
                    description="A-Mi source fuzzer",
                    help="Generate more A-Mi source code.")
    fuzz_input = fuzz_sub.add_parser("input",
                    description="A-Mi input fuzzer",
                    help="Generate input to existing A-Mi code.")

    FuzzUI.add_arguments(fuzz_ami)
    fuzz_ami.add_argument("-n", "--num",
                    dest="fuzz_ami_num",
                    type=int,
                    default=32,
                    metavar="NUM",
                    help="The number of new programs to generate (default: 32).")
    
    fuzz_input.add_argument("-n", "--num",
                    dest="fuzz_input_num",
                    type=int,
                    default=8,
                    metavar="NUM",
                    help="The number of new inputs to generate per program (default: 8).")
    fuzz_input.add_argument("--min",
                    dest="fuzz_input_min",
                    type=int,
                    default=-64,
                    metavar="NUM",
                    help="The minimum integer that may be generated for a program input (default: -64).")
    fuzz_input.add_argument("--max",
                    dest="fuzz_input_max",
                    type=int,
                    default=64,
                    metavar="NUM",
                    help="The maximum integer that may be generated for a program input (default: 64).")

    
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
    stats_parser.add_argument("--baseline",
                    dest="ref",
                    metavar="OPT",
                    default="-",
                    help="Specify an optimisation to serve as the baseline for the remaining data (or use \"-\" to refer to the original source code).")

    args = argparser.parse_args()
    PrinterUI.arg_init(args)

    multi = MultiUI.arg_init(args)
    tfmanager = TestFileUI.arg_init(args)

    tfmanager.verify_folder_integrity()
    tfmanager.delete_outdated()

    match args.type:

        case "opt":
            if args.opt_file is not None:
                try:
                    with open(args.opt_file, 'r') as opt_file:
                        passlines = [OptUI.parse_pipeline(line)
                                        for line in opt_file.readlines()
                                        if len(line.strip()) > 0]
                except FileNotFoundError:
                    utils.printing.perror(f"Opt file {args.opt_file} does not exist.")
                    exit(99)
            else:
                passlines = [[]]

            for line in passlines:
                opter = OptUI.arg_init(args)
                for Pass, pargs, pkwargs in line:
                    opter.append_pass(Pass, pargs, pkwargs)
                utils.printing.phidden(f"batch_opt :: {', '.join(opter.opts_cl)}")
                res = batch_opt(tfmanager, multi, opter, meta=args.meta, fresh=args.fresh_opt)
                if any(ec for _, ec in res.items()):
                    exit(99)

        case "fuzz":

            match args.fuzz_type:

                case "ami":
                    fuzz = FuzzUI.arg_init(args)
                    batch_fuzz_ami(tfmanager, multi, fuzz, num=args.fuzz_ami_num)

                case "input":
                    batch_fuzz_input(tfmanager, multi, num=args.fuzz_input_num, intmin=args.fuzz_input_min, intmax=args.fuzz_input_max)

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
                run_code_stats(tfmanager, multi, stats, ref=args.ref)
            else:
                run_trace_stats(tfmanager, multi, stats, ref=args.ref)
