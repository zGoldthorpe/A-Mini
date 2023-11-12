"""
Batch optimisation
====================
Goldthorpe

Optimise all ami code in tests/code/ with specified passes for perusing.
The optimised code is saved in tests/code.vfy/
"""
#TODO: make modular

import argparse
import os
import shutil
import subprocess
import time

argparser = argparse.ArgumentParser(
                description="Batch optimiser")

argparser.add_argument("folders",
            nargs='*',
            action="store",
            help="Indicate which folders to crawl (default: code/).")
argparser.add_argument("-p", "--add-pass",
            dest="passes",
            action="append",
            help="Append pass as in `amo.py`")
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
            help="Save optimisation debug messages.")
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


if len(args.folders) == 0:
    # default folder; crawl entire codebase
    args.folders = ["code/"]

for folder in args.folders:
    # ensure all folders exist
    if not os.path.exists(folder):
        print("Cannot find", folder)
        exit(-1)
    if not os.path.isdir(folder):
        print(folder, "is not a directory!")
        exit(-1)

if args.clean:
    for folder in args.folders:
        for path, folders, _ in os.walk(folder):
            for fld in folders:
                if fld.endswith(".vfy"):
                    to_remove = os.path.join(path, fld)
                    print("Removing", to_remove)
                    shutil.rmtree(to_remove)
    exit(0)

if args.passes is None:
    print("Batch optimiser requires optimisation passes!")
    exit(-1)

pass_name = '.'.join("".join(opt.split()) for opt in args.passes)

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

### collect A-Mi files to compile ###

amis = []
for folder in args.folders:
    for path, _, files in os.walk(folder):
        if any(fld.endswith(".vfy") for fld in path.split(os.path.sep)):
            continue
        for file in files:
            if file.endswith(".ami"):
                amis.append(os.path.join(path, file))

width = max(len(ami) for ami in amis) + 2

for ami in amis:
    print(f"{ami: <{width}}", end='', flush=True)

    name = os.path.splitext(ami)[0] # name of relevant folders

    vfy = name + ".vfy"

    if not os.path.exists(vfy):
        shutil.os.makedirs(vfy)

    fname = os.path.join(vfy, f"{pass_name}.ami")
    stderr_f = os.path.join(vfy, f"{pass_name}.log")
    with open(stderr_f, 'w') as stderr:
        try:
            start_time = time.time()
            subprocess.run(["python3", "amo.py", ami, "--output", fname] + amo_args,
                stderr=stderr,
                timeout=args.timeout,
                check=True, # check exit code
                )
            end_time = time.time()
        except subprocess.TimeoutExpired as e:
            print(f"\033[31mTLE({e.timeout:.3f}s)\033[m")
            continue
        except subprocess.CalledProcessError as e:
            print(f"\033[31mERR({e.returncode})\033[m")
            continue
        print(f"\033[32mDONE({end_time-start_time:.3f}s)\033[m")
