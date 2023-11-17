"""
Statistics
============
Goldthorpe
"""

from ui.errors import perror, die, unexpected

import utils.printing

import ampy.types

def pstructure(*args, **kwargs):
    utils.printing.Printing.formatted("\033[2m", "\033[m", *args, **kwargs)
def pval(*args, good=False, best=False, bad=False, worst=False, **kwargs):
    utils.printing.Printing.formatted(
            "\033[41m" if bad and worst and not best else
            "\033[32;41m" if good and worst and not best else
            "\033[31m" if (bad and not good) or (worst and not best) else
            "\033[42m" if good and best and not worst else
            "\033[31;42m" if bad and best and not worst else
            "\033[32m" if (good and not bad) or (best and not worst) else
            "", "\033[m", *args, **kwargs)
def phead(*args, **kwargs):
    utils.printing.Printing.formatted("\033[4m", "\033[m", *args, **kwargs)

class StatUI:

    @classmethod
    def add_arguments(cls, parser):
        
        parser.add_argument("-s", "--style",
                        dest="SUIstyle",
                        choices=("pretty", "csv", "latex"),
                        default="pretty",
                        help="Style for the output data (default: pretty).")
        parser.add_argument("-r", "--relative",
                        dest="SUIrelative",
                        choices=('+', 'x', '+%', 'x%'),
                        const='x',
                        nargs='?',
                        help="Produce data relative to a baseline, where relativity is measured additively (+), multiplicatively (x), or additively/multiplicatively as a percentage.")
        parser.add_argument("-p", "--prec",
                        dest="SUIfloat",
                        metavar="INT",
                        type=int,
                        default=3,
                        help="If the statistics are floating point or percentages, specify the number of digits after the decimal to display (default: 3).")

    @classmethod
    def arg_init(cls, parsed_args):

        return cls(style=parsed_args.SUIstyle,
                relative=parsed_args.SUIrelative,
                prec=parsed_args.SUIfloat)

    def __init__(self, style="pretty", relative=None, baseline=None, prec=3, flip=False):
        self._style = style
        self._relative = relative
        self._prec = prec

    def print_stats(self, header, subjects:dict, params:list, ref=None, flip=False):
        """
        subjects: dict mapping subj name to subj argument
        params: list of pairs (param_name, param_func), where the latter
                takes a subj argument as input.

        ref must be one of the subjects, else None
        If stats are relative, a non-None ref is required
        
        By default, larger values are considered \"better\". If stats are
        relative, \"flip\" will reverse operands: comparisons default to
        \"value - baseline\" and \"value / baseline\". If stats are absolute,
        \"flip\" only affects output display.
        """
        if self._relative is not None and ref is None:
            die("Relative statistics require specifying a baseline!")

        if ref is not None:
            if ref not in subjects:
                die(f"Statistic subjects do not include the baseline {ref}.")

            baseline = { param : func(subjects[ref])
                            for param, func in params }
        else:
            baseline = None
        
        def to_str(val):
            mathmode = False
            end = ''
            modifier = ''
            if isinstance(val, int):
                mathmode = True
                modifier = 'd'
            if isinstance(val, float):
                mathmode = True
                modifier = f".{self._prec}f"
                if val > 1e25:
                    return r"$\infty$" if self._style == "latex" else "inf"
            if self._relative is not None:
                if self._relative.startswith('+'):
                    modifier = '+' + modifier
                if self._relative.startswith('x'):
                    end = r'\times' if self._style == "latex" else 'x'
                if self._relative.endswith('%'):
                    val *= 100
                    end = r'\%' if self._style == "latex" else '%'
            out = f"{val:{modifier}}{end}"
            if mathmode and self._style == "latex":
                out = f"${out}$"
            return out

        def modify(param, func=lambda x: x):
            # modify function if computation is relative
            match self._relative:
                case None:
                    return func
                case '+':
                    if flip:
                        return lambda arg: baseline[param] - func(arg)
                    return lambda arg: func(arg) - baseline[param]
                case '+%':
                    if flip:
                        return lambda arg: (baseline[param] - func(arg))/(baseline[param]+1e-100)
                    return lambda arg: (func(arg) - baseline[param]) / (baseline[param]+1e-100)
                case 'x' | 'x%':
                    if flip:
                        return lambda arg: baseline[param] / (func(arg)+1e-100)
                    return lambda arg: func(arg) / (baseline[param]+1e-100)
                case _:
                    die(f"Unrecognised relativity specifier {self._relative}.")

        table = { param : { subj : modify(param, func)(arg)
                            for subj, arg in subjects.items() }
                        for param, func in params }
        printable = { param : { subj : to_str(value)
                            for subj, value in data.items() }
                        for param, data in table.items() }
        
        maxlen = { subj : max(len(subj),
                            max(len(printable[param][subj])
                                for param in printable))
                        for subj in subjects }

        topval = { param : max(table[param][subj]
                        for subj in subjects if subj != ref)
                    for param, _ in params }
        botval = { param : min(table[param][subj]
                        for subj in subjects if subj != ref)
                    for param, _ in params }

        if flip and self._relative is None:
            # only in this case, the lowest value is the best
            topval, botval = botval, topval

        maxparamlen = max(len(header),
                        max(len(param) for param in table))

        sep = (' , ' if self._style == 'csv' else
                ' | ' if self._style == 'pretty' else ' & ')
        end=" \\\\\n" if self._style == "latex" else '\n'

        # print header
        if self._style == "latex":
            if baseline is not None:
                pstructure(fr"\begin{{tabular}}{{r||c|{'c'*(len(subjects)-1)}}}")
            else:
                pstructure(fr"\begin{{tabular}}{{r|{'c'*len(subjects)}}}")
        phead(end=f"{header: ^{maxparamlen}}")

        subjects_sorted = sorted(subjects, key=lambda s: (s!=ref, s))
        for subj in subjects_sorted:
            pstructure(end=sep)
            phead(end=f"{subj: ^{maxlen[subj]}}")
        pstructure(end=end)

        if self._style == "latex":
            pstructure(fr"\{'hline%':-<{maxparamlen + sum(3+maxlen[subj] for subj in subjects)}}")
        elif self._style == "pretty":
            pstructure('-'*maxparamlen, end="-+-")
            pstructure("-+-".join('-'*maxlen[subj]
                            for subj in subjects_sorted))

        for param, _ in params:
            print(end=f"{param: ^{maxparamlen}}")
            data = table[param]
            outs = printable[param]
            for subj in subjects_sorted:
                pstructure(end=sep)
                val = data[subj]
                out = f"{outs[subj]: >{maxlen[subj]}}"
                if subj == ref:
                    pstructure(end=out)
                    continue
                pval(end=out,
                        good = ref is not None and
                            (flip ^ (val > data[ref])),
                        bad = ref is not None and
                            (flip ^ (val < data[ref])),
                        best = val == topval[param],
                        worst = val == botval[param])
            pstructure(end=end)

        # wrap up
        if self._style == "latex":
            pstructure(r"\end{tabular}")

def get_cfg_stats(cfg):
    """
    Returns a dict of information:
        num_blocks
        num_instructions
        num_vars
        num_phi
    """
    ret = dict(
            num_blocks=len(cfg),
            num_instructions=0,
            num_vars=0,
            num_phi=0,
            )
    var_set = set()
    for block in cfg:
        ret["num_instructions"] += len(block)
        for I in block:
            if isinstance(I, ampy.types.DefInstructionClass):
                var_set.add(I.target)
            if isinstance(I, ampy.types.PhiInstruction):
                ret["num_phi"] += 1

    ret["num_vars"] = len(var_set)

    return ret

def get_trace_stats(trace):
    """
    Takes a string containing trace output.
    Returns a dict of information:
        num_instructions
        num_branches (number of conditional branches visited)
        num_blocks
    """
    lines = trace.splitlines()
    return dict(
            num_instructions=len(list(filter(
                lambda l: "::" not in l and not l.startswith('@'), lines))),
            num_branches=len(list(filter(
                lambda l: l.startswith("branch"), lines))),
            num_blocks=len(list(filter(
                lambda l: l.startswith("@"), lines))))

def name_compressor(names):
    """
    Reduces a list of names to a list of 'critical' letters,
    where a letter is 'critical' if it has several siblings in
    the trie corresponding to the set of names

    returns dict mapping names to compressed strings
    """
    if len(names) == 1:
        return { name : name[0] for name in names }
    # first, build trie with no info
    trie = {}
    for name in names:
        ptr = trie
        for c in name:
            ptr = ptr.setdefault(c, {})
        ptr[0] = name # indicate that this is also a name
    def reduced(name):
        ptr = trie
        out = ""
        for c in name:
            if len(ptr) > 1:
                out += c
            ptr = ptr[c]
        return out
    return { name : reduced(name) for name in names }
