"""
Test files
============
Goldthorpe
"""

import os
import shutil

from ui.errors import perror, die, unexpected

class TestFileUI:

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument("-f", "--add-folder",
                        dest="TFUIfolders",
                        metavar="FOLDER",
                        action="append",
                        help="Specify which folders to test on.")
        parser.add_argument("-X", "--clear",
                        dest="TFUIclear",
                        action="store_true",
                        help="Delete output folders.")

    def __init__(self, parsed_args):

        if parsed_args.TFUIfolders is None:
            self.folders = ["code/"]
        else:
            self.folders = parsed_args.TFMfolders

        self._scan()

        if parsed_args.TFUIclear:
            # after all that, if the user wanted to clear the data, then so be it
            self.delete_data()


    def _scan(self):
        """
        Scan folders for vfy and output files.
        """
        self._tests = {}
        # maps input ami files to a dict of information
        # self._tests[ami]["@in"] -> set of relative input tests
        # self._tests[ami]["@out"] -> list of outputs and traces
        # self._tests[ami][opt] -> dict corresponding to optimisation
        #                 ...["@log"] -> if key exists, log file exists
        #                 ...["@out"] -> set of outputs, traces, and diffs
        for folder in self.folders:
            if not os.path.exists(folder):
                die(f"Path {folder} does not exist!")
            if not os.path.isdir(folder):
                die(f"Path {folder} is not a folder!")

            for path, folders, files in os.walk(folder):
                if path.endswith(".vfy"):
                    ami = os.path.splitext(path)[0]
                    self._tests.setdefault(ami, {})

                    for file in sorted(files):
                        opt = os.path.splitext(file)[0]
                        if file.endswith(".ami"):
                            self._tests[ami][opt] = {}
                        if file.endswith(".log"):
                            # ami file would come first
                            if opt in self._tests[ami]:
                                self._tests[ami][opt]["@log"] = []

                    for fld in folders:
                        if fld.endswith(".out"):
                            opt = os.path.splitext(fld)[0]
                            if opt in self._tests[ami]:
                                self._tests[ami][opt]["@out"] = set(os.listdir(os.path.join(path, fld)))
                                # all paths are relative

                if ".vfy" in path:
                    continue

                for file in files:
                    ami = os.path.join(path, os.path.splitext(file)[0])
                    if file.endswith(".ami"):
                        self._tests.setdefault(ami, {})

                for fld in folders:
                    ami = os.path.join(path, os.path.splitext(fld)[0])
                    if fld.endswith(".in"):
                        self._tests.setdefault(ami, {})["@in"] = set(os.listdir(os.path.join(path, fld)))
                        # path is relative
                    if fld.endswith(".out"):
                        self._tests.setdefault(ami, {})["@out"] = set(os.listdir(os.path.join(path, fld)))

    
    def verify_folder_integrity(self):
        """
        Ensure source files exist for input / vfy folders
        """
        for ami in self._tests:
            amif = f"{ami}.ami"
            if not os.path.exists(amif):
                if "@in" in self._tests[ami]:
                    die(f"Expected file\n\t{amif}\ndoes not exist for corresponding input folder {ami}.in/")
                die(f"Expected file\n\t{amif}\ndoes not exist for corresponding vfy folder {ami}.vfy/")

    def delete_data(self):
        """
        Delete all output and vfy folders.
        """
        for ami in self._tests:
            vfy = self.get_test_vfy_folder(ami)
            out = self.get_test_output_folder(ami)
            if os.path.exists(vfy):
                print("Deleting", vfy)
                shutil.rmtree(vfy)
            if os.path.exists(out):
                print("Deleting", out)
                shutil.rmtree(out)
        # refresh after the deletion
        self._scan()

    def delete_outdated(self):
        """
        Output and vfy files are dependent on the source code and input tests.
        Delete the former if older than their dependencies.
        (Assumes `verify_folder_integrity` has passed.)
        """
        for ami, data in list(self._tests.items()):
            amimtime = os.path.getmtime(self.get_test_ami(ami))

            # check for updates in input data first
            if "@in" in data:
                for inf in data["@in"]:
                    if not inf.endswith(".in"):
                        continue
                    infmtime = os.path.getmtime(self.get_test_input_fpath(ami, inf))
                    outf = os.path.splitext("inf")[0] + ".out"

                    # remove outdated output
                    if outf in data.get("@out", set()):
                        fullout = self.get_test_corresponding_output(ami, inf)
                        if not os.path.exists(fullout):
                            continue
                        outfmtime = os.path.getmtime(fullout)
                        if infmtime < outfmtime:
                            continue
                        self._tests[ami]["@out"].remove(outf)
                        if os.path.exists(fullout):
                            print(f"{fullout} is out of date.")
                            os.remove(fullout)


                    # remove outdated opt output
                    for opt, odata in data.items():
                        if opt.startswith('@'):
                            continue
                        if outf in odata.get("@out", set()):
                            fullout = self.get_test_opt_corresponding_output(ami, opt, inf)
                            if not os.path.exists(fullout):
                                continue
                            outfmtime = os.path.getmtime(fullout)
                            if infmtime < outfmtime:
                                continue
                            self._tests[ami][opt]["@out"].remove(outf)
                            if os.path.exists(fullout):
                                print(f"{fullout} is out of date.")
                                os.remove(fullout)

            # now check for updates in source file
            out_fld = self.get_test_output_folder(ami)
            if os.path.exists(out_fld):
                outmtime = os.path.getmtime(out_fld)
                if outmtime <= amimtime:
                    del self._tests[ami]["@out"]
                    if os.path.exists(out_fld):
                        print(f"{out_fld} is out of date.")
                        shutil.rmtree(out_fld)
            vfy_fld = self.get_test_vfy_folder(ami)
            if os.path.exists(vfy_fld):
                vfymtime = os.path.getmtime(vfy_fld)
                if vfymtime <= amimtime:
                    for opt in list(filter(lambda k: not k.startswith('@'), data)):
                        del self._tests[ami][opt]
                    if os.path.exists(vfy_fld):
                        print(f"{vfy_fld} is out of date.")
                        shutil.rmtree(vfy_fld)

    @property
    def tests(self):
        """
        Get tuple of test keys
        """
        return tuple(self._tests.keys())

    def get_test_ami(self, test):
        """
        Get the ami file corresponding to `test`
        """
        return f"{test}.ami"
    
    def get_test_input_folder(self, test):
        """
        Get the input folder for the test
        """
        return f"{test}.in"
    
    def get_test_input_files(self, test):
        """
        Get tuple of input files for `test`
        """
        return tuple(filter(lambda f: f.endswith(".in"),
            self._tests.get(test, {}).get("@in", [])))

    def get_test_input_fpath(self, test, file):
        """
        Get file path to particular file in input folder
        """
        return os.path.join(self.get_test_input_folder(test), file)
    
    def get_test_output_folder(self, test):
        return f"{test}.out"

    def get_test_corresponding_output(self, test, inputfile):
        """
        Get file path to output file corresponding to input filename.
        """
        file = os.path.splitext(inputfile)[0] + ".out"
        return os.path.join(self.get_test_output_folder(test), file)

    def get_test_output_files(self, test):
        return tuple(filter(lambda f: f.endswith(".out"),
            self._tests.get(test, {}).get("@out", [])))

    def get_test_output_fpath(self, test, file):
        return os.path.join(self.get_test_output_folder(test), file)

    def get_test_vfy_folder(self, test):
        return f"{test}.vfy"

    def get_test_corresponding_opt(self, test, opt):
        """
        opt is a chosen name representing optimisation (not an ami file)
        """
        return os.path.join(self.get_test_vfy_folder(test), f"{opt}.ami")

    def get_test_opts(self, test):
        return tuple(filter(lambda p: not p.startswith('@'),
            self._tests.get(test, {})))

    def get_test_opt_corresponding_log(self, test, opt):
        return os.path.join(self.get_test_vfy_folder(test), f"{opt}.log")

    def get_test_opt_corresponding_output(self, test, opt, inputfile):
        file = os.path.splitext(inputfile)[0] + ".out"
        return os.path.join(self.get_test_vfy_folder(test), f"{opt}.out", file)
