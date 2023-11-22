"""
Multiprocessing
=================
Goldthorpe
"""

import collections
import multiprocessing
import os
import random
import shutil
import sys
import time

import utils.debug
import utils.printing

from ui.errors import perror, die, unexpected


class MultiUI:

    @classmethod
    def add_arguments(cls, parser):

        parser.add_argument("-n", "--max-procs",
                    dest="MUImax_procs",
                    metavar="MAX",
                    action="store",
                    type=int,
                    default=32,
                    help="Specify maximum number of processes to fork and manage (default: 32).")
        parser.add_argument("-T", "--timeout",
                    dest="MUItimeout",
                    metavar="FLOAT",
                    action="store",
                    type=float,
                    help="Specify timeout (in seconds) for each process.")

    @classmethod
    def fopen(cls, file, mode='r'):
        folder = os.path.split(file)[0]
        try:
            shutil.os.makedirs(folder)
        except FileExistsError:
            pass
        return open(file, mode)

    @classmethod
    def arg_init(cls, parsed_args):
        return cls(max_procs=parsed_args.MUImax_procs,
                timeout=parsed_args.MUItimeout)

    def __init__(self, max_procs=32, timeout=None):

        self.max_procs = max_procs
        self.timeout = timeout
        
        self._proc_queue = collections.deque()
        self._running_procs = {} # map from ID to process

    def prepare_process(self, ID:str, *, target, args=(), kwargs={}, stdin=None, stdout=None, stderr=None):
        """
        Add a process intended for running asynchronously with others.
        """
        def wrapped_target():
            # multiprocessing processes close stdin by default
            # so we need to circumvent this
            if stdin is not None:
                sys.stdin = self.fopen(stdin, 'r')
            if stdout is not None:
                sys.stdout = self.fopen(stdout, 'w')
            if stderr is not None:
                sys.stderr = self.fopen(stderr, 'w')
            target(*args, **kwargs)

        self._proc_queue.append((ID, wrapped_target))

    @classmethod
    def print_progressbar(cls, completed, queued, total):
        if total == 0:
            perc = 100
            qperc = 0
        else:
            perc = (completed * 100) // total
            qperc = (queued * 100) // total
        msg = f"{completed} / {total}"
        if utils.printing.Printing.can_format:
            msg = f"{msg: ^100}"
            utils.printing.Printing.formatted("\033[0G[\033[42;30m", "\033[m",
                    msg[:perc], end='')
            utils.printing.Printing.formatted("\033[43;30m", "\033[m", msg[perc:perc+qperc], end='')
            utils.printing.Printing.formatted("\033[41;37m", "\033[m", msg[perc+qperc:], end='')

            print(']', end='', flush=True)
        else:
            print('\b'*102, end='')
            print('[', end='')
            print("#"*perc, end='')
            print("_"*qperc, end='')
            if len(msg) + perc + qperc + 1 < 100:
                print(' ', end=msg)
                print(' '*(100-perc-qperc-len(msg)-1), end='')
            else:
                print(' '*(100-perc-qperc), end='')
            print(']', end='', flush=True)

    def execute(self):
        """
        Run all prepared processes asynchronously.
        Halts parent process until all prepared processes terminate.
        Returns a dictionary from ID to exit codes
        """
        overall_time = time.time()
        exit_code = {}
        runtime = {}

        # in case processes are inserted where all the slow processes are
        # put together, shuffle things around to make the runtime more
        # steady
        random.shuffle(self._proc_queue)

        total = len(self._proc_queue)
        done = 0
        if not utils.debug.enabled:
            self.print_progressbar(done, 0, total)
        # NB: measures realtime passage, not processing time
        newdone = 0
        killed = set()
        while True:
            if len(self._proc_queue) > 0:
                if len(self._running_procs) < self.max_procs:
                    ID, target = self._proc_queue.popleft()
                    utils.debug.print(ID, "initialising process.")
                    try:
                        self._running_procs[ID] = multiprocessing.Process(target=target)
                        self._running_procs[ID].start()
                        runtime[ID] = time.time()
                    except OSError:
                        # too many processes open
                        if ID in self._running_procs:
                            del self._running_procs[ID]
                        utils.debug.print(ID, "could not spawn; requeuing...",
                                    print_func=utils.printing.perror)
                        self._proc_queue.appendleft((ID, target))
                        time.sleep(0.1)
            elif len(self._running_procs) == 0:
                break
            
            # remove finished processes
            for ID, proc in list(self._running_procs.items()):
                if not proc.is_alive():
                    runtime[ID] = time.time() - runtime[ID]
                    exit_code[ID] = proc.exitcode
                    if ID not in killed:
                        if exit_code[ID] != 0:
                            if not utils.debug.enabled:
                                # so output is not on same line as progress bar
                                print()
                            perror(f"Process {ID} terminated with nonzero exit code {exit_code[ID]}.")
                        else:
                            utils.debug.print(ID, f"process terminated in {runtime[ID]:.3f}s.",
                                    print_func=utils.printing.psuccess)
                    del self._running_procs[ID]
                    newdone += 1
                    proc.close()
                elif ID in killed:
                    continue
                elif self.timeout is not None:
                    if time.time() - runtime[ID] > self.timeout:
                        # process timed out
                        if not utils.debug.enabled:
                            print()
                        perror(f"Process {ID} timed out.")
                        proc.kill()
                        killed.add(ID)
            if newdone > 0:
                # the timing is only for when we cannot refresh the
                # progress bar (due to inability to format)
                done += newdone
                newdone = 0
                if not utils.debug.enabled:
                    self.print_progressbar(done, len(self._running_procs), total)

        if not utils.debug.enabled:
            print()

        overall_time = time.time() - overall_time
        utils.debug.print("multi", f"multiprocessing terminated in {overall_time:.3f}s.")
        return exit_code

