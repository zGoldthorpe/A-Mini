"""
Batch testing
===============
Goldthorpe

Will run all ami code in tests/code.vfy/ against provided test input, and
compare the output with that coming from the original code in tests/code/.
"""
#TODO: combine with batch_opt

import argparse
import os
import shutil
import subprocess
import time

argparser = argparse.ArgumentParser(
                description="Batch tester")

argparser.add_argument("folders",
            nargs='*',
            action="store",
            help="Indicate which folders to crawl (default: code/).")
argparser.add_argument("-T", "--timeout",
            dest="timeout",
            action="store",
            type=float,
            help="Set timeout for each execution, in seconds.")

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

### Determine interpreter arguments ###

ami_args = ["--suppress-breakpoint", "--trace", "--plain"]

### Compute output for expected files ###

print("Generating test cases...")
testcases = {} # maps an ami file to a list of test cases
for folder in args.folders:
    for path, _, files in os.walk(folder):
        if any(fld.endswith(".vfy") for fld in path.split(os.path.sep)):
            continue
        for file in files:
            if file.endswith(".ami"):
                ami = os.path.join(path, file)
                testins = os.path.splitext(ami)[0] + ".in"
                if not os.path.exists(testins):
                    continue
                if not os.path.isdir(testins):
                    print(f"{testins} is not a folder! Aborting.")
                    exit(-1)
                testcases[ami] = sorted(filter(lambda t: t.endswith(".in"), os.listdir(testins)))

test_width = max(max(len(ami), max(4+len(test) for test in testcase))
                for ami, testcase in testcases.items()) + 2

for ami, testcase in testcases.items():
    print(ami)
    testouts = os.path.splitext(ami)[0] + ".out"
    testins = os.path.splitext(ami)[0] + ".in"
    if not os.path.exists(testouts):
        shutil.os.makedirs(testouts)
    if not os.path.isdir(testouts):
        print(f"{testouts} is not a folder! Aborting.")
        exit(-1)
    for testin in testcase:
        testout = os.path.splitext(testin)[0] + ".out"
        trace = os.path.splitext(testin)[0] + ".trace"
        print(f"    {testin: <{test_width-4}}", end='', flush=True)
        with (open(os.path.join(testins, testin), 'r') as stdin,
                open(os.path.join(testouts, testout), 'w') as stdout,
                open(os.path.join(testouts, trace), 'w') as stderr):
            try:
                start_time = time.time()
                subprocess.run(["python3", "ami.py", ami] + ami_args,
                        stdin=stdin,
                        stdout=stdout,
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

### Test optimisations ###
print("Testing optimisations...")

opts = {} # maps an ami file to its original
for folder in args.folders:
    for path, _, files in os.walk(folder):
        if not path.endswith(".vfy"):
            continue
        for file in files:
            if file.endswith(".ami"):
                # splitext on path will remove the ".vfy"
                orig = os.path.splitext(path)[0] + ".ami"
                if orig not in testcases:
                    continue
                opts[os.path.join(path, file)] = orig

if len(opts) == 0:
    print("No optimisations to test.")
    exit()

width = max(test_width, max(len(opt) for opt in opts) + 2)
for opt, orig in opts.items():
    print(opt)
    testins = os.path.splitext(orig)[0] + ".in"
    testouts = os.path.splitext(orig)[0] + ".out"
    optouts = os.path.splitext(opt)[0] + ".out"
    if not os.path.exists(optouts):
        shutil.os.makedirs(optouts)

    for testin in testcases[orig]:
        print(f"    {testin: <{width-4}}", end='', flush=True)
        optout = os.path.splitext(testin)[0] + ".out"
        trace = os.path.splitext(testin)[0] + ".trace"
        with (open(os.path.join(testins, testin), 'r') as stdin,
                open(os.path.join(optouts, optout), 'w') as stdout,
                open(os.path.join(optouts, trace), 'w') as stderr):
            try:
                start_time = time.time()
                subprocess.run(["python3", "ami.py", opt] + ami_args,
                        stdin=stdin,
                        stdout=stdout,
                        stderr=stderr,
                        timeout=args.timeout,
                        check=True,
                        )
                end_time = time.time()
            except subprocess.TimeoutExpired as e:
                print(f"\033[31mTLE({e.timeout:.3f}s)\033[m")
                continue
            except subprocess.CalledProcessError as e:
                print(f"\033[31mERR({e.returncode})\033[m")
                continue

        # now check outputs
        expected_f = os.path.join(testouts, optout)
        received_f = os.path.join(optouts, optout)
        with open(expected_f, 'r') as file:
            expected = file.readlines()
        with open(received_f, 'r') as file:
            received = file.readlines()

        if received != expected:
            diff = os.path.splitext(testin)[0] + ".diff"
            with open(os.path.join(optouts, diff), 'w') as stdout:
                subprocess.run(["diff", expected_f, received_f], stdout=stdout)
            print(f"\033[31mDIFF({end_time-start_time:.3f}s)\033[m")
            continue
        print(f"\033[32mACC({end_time-start_time:.3f}s)\033[m")
