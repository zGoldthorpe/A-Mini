from ampy.types import CFG
from ampy.reader import CFGBuilder

from opt.tools import OptList

from tests.tools import PythonExecutionTestSuite

class MetaTestSuite(PythonExecutionTestSuite):

    def __repr__(self):
        return f"MetaTestSuite({self.name})"

    @PythonExecutionTestSuite.test
    def analyse_meta(self, opt_cls, args, kwargs, code, meta):
        """
        opt_cls
            Opt class
        args, kwargs
            initialisation parameters for opt
        code
            list of strings of A-Mi code (one line per element)
        meta
            a dict mapping strings or slices to expected lists of values
            Keys are of one of the following forms:
            - "arg" (CFG-level meta argument)
            - ("block", "arg") (block-level meta argument)
            - ("block", idx:int, "arg") (instruction-level meta argument)
        metadata not included in meta variable are not tested
        """
        cfg = CFGBuilder().build(*code)
        opt = opt_cls(cfg, OptList(), *args, **kwargs)
        for key in meta:
            if isinstance(key, tuple):
                slicekey = slice(cfg[key[0]], key[1], key[2] if len(key) > 2 else None)
            else:
                slicekey = key
            if opt[slicekey] != meta[key]:
                self._error(f"{opt_cls.ID} opt expected to produce value {meta[key]} for key {key}, but instead produces {opt[key]}.")
                return False, dict(
                        type="key-not-found",
                        cfg=cfg,
                        opt=opt,
                        key=key,
                        expected=meta[key],
                        received=opt[key])

        return True, dict(cfg=cfg, opt=opt, meta=meta)
