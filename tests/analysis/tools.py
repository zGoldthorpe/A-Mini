from ampy.types import CFG
from ampy.reader import CFGBuilder

from analysis.tools import AnalysisList

from tests.tools import PythonExecutionTestSuite

class MetaTestSuite(PythonExecutionTestSuite):

    def __repr__(self):
        return f"MetaTestSuite({self.name})"

    @PythonExecutionTestSuite.test
    def analyse_meta(self, analysis_cls, args, kwargs, code, meta):
        """
        analysis_cls
            Analysis class
        args, kwargs
            initialisation parameters for analysis
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
        analysis = analysis_cls(cfg, AnalysisList(), *args, **kwargs)
        for key in meta:
            if isinstance(key, tuple):
                slicekey = slice(cfg[key[0]], key[1], key[2] if len(key) > 2 else None)
            else:
                slicekey = key
            if analysis[slicekey] != meta[key]:
                self._error(f"{analysis_cls.ID} analysis expected to produce value {meta[key]} for key {key}, but instead produces {analysis[key]}.")
                return False, dict(
                        type="key-not-found",
                        cfg=cfg,
                        analysis=analysis,
                        key=key,
                        expected=meta[key],
                        received=analysis[key])

        return True, dict(cfg=cfg, analysis=analysis, meta=meta)
