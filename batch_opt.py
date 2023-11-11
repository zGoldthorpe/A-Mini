"""
Batch optimisation
====================
Goldthorpe

Optimise all ami code in tests/code/ with specified passes for perusing.
The optimised code is saved in tests/code.vfy/
"""

import argparse
import os
import shutil
import subprocess
import time

if not os.path.exists("amo.py"):
    print("Please run script from folder containing amo.py")
    exit(0)

argparser = argparse.ArgumentParser(
                description="Batch optimiser")

argparser.add_argument("passes",
            action="store",
            nargs='*',
            help="List of optimisation passes to give to amo.py")
argparser.add_argument("-M", "--omit-metadata",
            dest="meta",
            action="store_false",
            help="Do not write metadata to output.")
argparser.add_argument("-f", "--frame",
            dest="frame",
            action="store",
            metavar='"L;W"',
            help="Specify the left margin charwidth and the code window for spacing. "
                 "Use '*' for either dimension to make it automatic.")
argparser.add_argument("-D", "--debug",
            dest="debug",
            action="store_true",
            help="Print optimisation debug messages.")
argparser.add_argument("-X", "--clean",
            dest="clean",
            action="store_true",
            help="Remove output files.")
argparser.add_argument("-T", "--timeout",
            dest="timeout",
            action="store",
            type=float,
            help="Set timeout for each opt call, in seconds.")

args = argparser.parse_args()

if args.clean:
    if os.path.exists("tests/code.vfy"):
        print("Removing tests/code.vfy/")
        shutil.rmtree("tests/code.vfy")
    exit(0)

pass_ext = '.'.join("".join(opt.split()) for opt in [''] + args.passes + ["ami"])

amo_args = []
amo_args.append("--plain") # always make output plain

for opt in args.passes:
    amo_args.append("--add-pass")
    amo_args.append(opt)
if not args.meta:
    amo_args.append("--omit-metadata")
if args.frame is not None:
    amo_args.append("--frame")
    amo_args.append(args.frame)
if args.debug:
    amo_args.append("--debug")

if not os.path.exists("tests/code.vfy"):
    os.mkdir("tests/code.vfy")


amis = []
for path, _, files in os.walk("tests/code"):
    for file in files:
        if file.endswith(".ami"):
            amis.append(os.path.join(path, file))
width = max(len(os.path.relpath(ami, 'tests/code')) for ami in amis) + 2

for ami in amis:
    print(f"{os.path.relpath(ami, 'tests/code'): <{width}}", end='', flush=True)
    path, fname = os.path.split(ami)
    path = path.replace("tests/code", "tests/code.vfy")

    if not os.path.exists(path):
        shutil.os.makedirs(path)

    fname = os.path.splitext(fname)[0] + pass_ext
    output = os.path.join(path, fname)
    with open(os.path.splitext(output)[0] + ".stdout", 'w') as stdout:
        with open(os.path.splitext(output)[0] + ".stderr", 'w') as stderr:
            try:
                start_time = time.time()
                subprocess.run(["python3", "amo.py", ami, "--output", output] + amo_args,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=args.timeout,
                    check=True, # check exit code
                    )
                end_time = time.time()
            except subprocess.TimeoutExpired:
                print(f"\033[31mTLE({args.timeout:.3f}s)\033[m")
                continue
            except subprocess.CalledProcessError as e:
                print(f"\033[31mERR({e.returncode})\033[m")
                continue
            print(f"\033[32mDONE({end_time-start_time:.3f}s)\033[m")
