"""
Multiprocessing
=================
Goldthorpe
"""

import collections
import multiprocessing
import os
import shutil
import sys
import time

import utils.debug

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
            def subwrapped_target(*w_args, **w_kwargs):
                if stdin is not None:
                    sys.stdin = self.fopen(stdin, 'r')
                target(*w_args, **w_kwargs)

            if stdout is not None:
                sys.stdout = self.fopen(stdout, 'w')
            if stderr is not None:
                sys.stderr = self.fopen(stderr, 'w')

            # for timing out, I don't know a better way than to
            # spawn a second process, which seems insane
            proc = multiprocessing.Process(target=subwrapped_target, args=args, kwargs=kwargs)
            proc.start()
            proc.join(timeout=self.timeout)
            exit(proc.exitcode)


        self._proc_queue.append((ID, wrapped_target))

    def execute(self):
        """
        Run all prepared processes asynchronously.
        Halts parent process until all prepared processes terminate.
        Returns a dictionary from ID to exit codes
        """
        overall_time = time.time()
        exit_code = {}
        runtime = {}
        # NB: measures realtime passage, not processing time
        while True:
            if len(self._proc_queue) > 0:
                if len(self._running_procs) < self.max_procs:
                    ID, target = self._proc_queue.popleft()
                    utils.debug.print(ID, "initialising process.")
                    self._running_procs[ID] = multiprocessing.Process(target=target)
                    self._running_procs[ID].start()
                    runtime[ID] = time.time()
            elif len(self._running_procs) == 0:
                break
            
            # remove finished processes
            for ID, proc in list(self._running_procs.items()):
                if not proc.is_alive():
                    runtime[ID] = time.time() - runtime[ID]
                    exit_code[ID] = proc.exitcode
                    if exit_code[ID] != 0:
                        perror(f"Process {ID} terminated with nonzero exit code {exit_code[ID]}.")
                    else:
                        utils.debug.print(ID, f"process terminated in {runtime[ID]:.3f}s.",
                                print_func=utils.printing.psuccess)
                    del self._running_procs[ID]

        overall_time = time.time() - overall_time
        utils.debug.print("multi", f"multiprocessing terminated in {overall_time:.3f}s.")
        return exit_code

