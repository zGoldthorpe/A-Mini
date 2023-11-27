"""
DOT generator
===============
Goldthorpe
"""

import re

from ui.errors import perror, die, unexpected

import ampy.types

class DotUI:

    @classmethod
    def add_arguments(cls, parser):

        parser.add_argument("-@", "--labels-only",
                        dest="DGUIlabels",
                        action="store_true",
                        help="Have the node consist only of the block label.")
        parser.add_argument("-x", "--latex",
                        dest="DGUIlatex",
                        action="store_true",
                        help="Prepare output to be called with `dot2tex -traw`.")
        parser.add_argument("--math",
                        dest="DGUImath",
                        action="store_true",
                        help="Output math-style pseudocode.")
        parser.add_argument("--simple-branch",
                        dest="DGUIbranch",
                        action="store_true",
                        help="Simplify the branch instruction readability.")
        parser.add_argument("--hide-phi-labels",
                        dest="DGUIphi",
                        action="store_true",
                        help="Hide the phi labels (NB: the order of arguments to the phi node will not necessarily correspond to the order of incoming edges to the node).")
        parser.add_argument("--nice",
                        dest="DGUInice",
                        action="store_true",
                        help="By default, shorthand for --math --simple-branch --hide-phi-labels; if --latex is enabled, then it is only shorthand for --math --simple")

    @classmethod
    def arg_init(cls, parsed_args):
        return cls(labels=parsed_args.DGUIlabels,
                    latex=parsed_args.DGUIlatex,
                    math=parsed_args.DGUImath | parsed_args.DGUInice,
                    branch=parsed_args.DGUIbranch | parsed_args.DGUInice,
                    phi=parsed_args.DGUIphi | (parsed_args.DGUInice and not parsed_args.DGUIlatex))

    def __init__(self, labels=False, latex=False, math=False, branch=False, phi=False):
        self.labels_only = labels
        self.latex = latex
        self.math = math
        self.simple_branch = branch
        self.no_phi_labels = phi

    def _rpo(self, cfg):
        seen = set()
        postorder = []
        def dfs(block):
            seen.add(block)
            for child in block.children:
                if child not in seen:
                    dfs(child)
            postorder.append(block)
        dfs(cfg.entrypoint)
        return list(reversed(postorder))

    def print_dot(self, cfg):
        if self.latex:
            return self.tex_dot(cfg)
        return self.plain_dot(cfg)

    ### plain DOT output ###

    def plain_dot(self, cfg):
        """
        Produce a plain DOT file
        """
        rpo = self._rpo(cfg)
        print("digraph {")
        if self.math:
            print("node [shape=Mrecord]")
        else:
            print("node [shape=Mrecord fontname=Courier]")
        for block in rpo:
            print(self.plain_node(block))

        for block in rpo:
            for child in block.children:
                print(f"{self.plain_label(block.label)}",
                        "->",
                        f"{self.plain_label(child.label)}",
                        "[style=dashed];" if len(block.children) == 2
                            and child.label == block.branch_instruction.iffalse
                            else ";"
                        )

        print("}")

    def plain_node(self, block):
        """
        Produce node for a plain DOT file
        """
        # node label needs to be sanitised
        label = self.plain_label(block.label)
        if self.labels_only:
            return f'{label} [label="{block.label[1:]}"];'
        repfun = self.plain_math if self.math else self.plain_repr
        content = r'\l'.join(filter(None, (repfun(I) for I in block)))
        return fr'{label} [label="{{{block.label}:\l |{{{content}\l}}}}"];'

    def plain_label(self, label):
        """
        Sanitise label for plain DOT file
        """
        return "block_" + label[1:].replace('_', '__').replace('.', '_')

    def plain_repr(self, I):
        if isinstance(I, ampy.types.BrkInstruction):
            return None
        if isinstance(I, (ampy.types.LeqInstruction, ampy.types.LtInstruction, ampy.types.LShiftInstruction)):
            return repr(I).replace('<', r'\<')
        if isinstance(I, ampy.types.RShiftInstruction):
            return repr(I).replace('>', r'\>')
        if isinstance(I, ampy.types.PhiInstruction) and self.no_phi_labels:
            return f"{I.target} = phi({', '.join(val for val, _ in I.conds)})"
        if isinstance(I, ampy.types.GotoInstruction) and self.simple_branch:
            return None
        if isinstance(I, ampy.types.BranchInstruction) and self.simple_branch:
            return f"if ({I.cond})"
        return repr(I)
    
    def plain_math(self, I):
        def reg(var):
            if not var.startswith('%'):
                return var
            if var[1].isdigit():
                return f"[{var[1:]}]"
            return var[1:]

        match type(I):

            case ampy.types.MovInstruction:
                return f"{reg(I.target)} := {reg(I.operand)}"

            case ampy.types.PhiInstruction:
                if self.no_phi_labels:
                    return f"{reg(I.target)} := phi({', '.join(reg(val) for val, _ in I.conds)})"
                return f"{reg(I.target)} := phi " + ", ".join(
                        f"[{reg(val)}, {cond}]" for val, cond in I.conds)

            case T if issubclass(T, ampy.types.BinaryInstructionClass):
                op1, op2 = map(lambda o: re.sub(r"-(.*)", r"(-\1)", reg(o)), I.operands)
                if issubclass(T, ampy.types.ArithInstructionClass):
                    match I.op:
                        case "%":
                            op = "mod"
                        case _:
                            op = I.op

                elif issubclass(T, ampy.types.BitwiseInstructionClass):
                    match I.op:
                        case "&":
                            op = "and"
                        case "|":
                            op = "or"
                        case "^":
                            op = "xor"
                        case "<<":
                            op = r"\<\<"
                        case ">>":
                            op = r"\>\>"
                        case _:
                            op = I.op
                elif issubclass(T, ampy.types.CompInstructionClass):
                    match I.op:
                        case "==":
                            op = '='
                        case "<":
                            op = r"\<"
                        case "<=":
                            op = r"\<="
                        case _:
                            op = I.op
                    # also override the return value in this case
                    return f"{reg(I.target)} := ({op1} {op} {op2})"

                return f"{reg(I.target)} := {op1} {op} {op2}"

            case ampy.types.GotoInstruction:
                if self.simple_branch:
                    return None
                return repr(I)
            
            case ampy.types.BranchInstruction:
                if self.simple_branch:
                    return f"if ({reg(I.cond)})"
                return fr"if ({reg(I.cond)}) goto {I.iftrue}\lgoto {I.iffalse}"

            case ampy.types.ExitInstruction:
                return "exit"

            case ampy.types.ReadInstruction:
                return f"{reg(I.target)} := read()"
            
            case ampy.types.WriteInstruction:
                return f"write({reg(I.operand)})"

            case _:
                # ignore breakpoints and unknowns
                return None

    ### LaTeX DOT output ###

    def tex_dot(self, cfg):
        """
        Produce a LaTeX DOT file
        """
        rpo = self._rpo(cfg)
        print("digraph {")
        print('node [shape=box style="rounded corners"]')
        for block in rpo:
            print(self.tex_node(block))

        for block in rpo:
            for child in block.children:
                print(f"{self.plain_label(block.label)}",
                        "->",
                        f"{self.plain_label(child.label)}",
                        "[style=dashed];" if len(block.children) == 2
                            and child.label == block.branch_instruction.iffalse
                            else ";"
                        )

        print("}")

    def tex_node(self, block):
        """
        Produce node for a LaTeX DOT file
        """
        # node label needs to be sanitised
        label = self.plain_label(block.label)
        texlabel = self.tex_label(block.label)
        if self.labels_only:
            return f'{label} [label="{block.label[1:]}"];'
        repfun = self.tex_math if self.math else self.tex_repr

        content = r' \\ '.join(filter(None, (repfun(I) for I in block)))
        front = "$" if self.math else r"\ttfamily"
        back = "$" if self.math else ""
        env = "array" if self.math else "tabular"
        return (fr'{label} [label="{front}\begin{{{env}}}{{l}}'
                fr'{texlabel}: \\\hline '
                fr'{content} \end{{{env}}}{back}"];').replace("\\", "\\\\")

    def tex_label(self, label):
        label = label.replace('_', r'\_')
        if self.math:
            return fr"\textsc{{{label[1:]}}}"
        return label
    
    def tex_repr(self, I):
        def sanitise(s):
            return s.replace('_', r'\_').replace('%', r'\%').replace('&', r'\&')

        if isinstance(I, ampy.types.BrkInstruction):
            return None
        if isinstance(I, ampy.types.PhiInstruction) and self.no_phi_labels:
            return sanitise(f"{I.target} = phi({', '.join(val for val, _ in I.conds)})")
        if isinstance(I, ampy.types.GotoInstruction) and self.simple_branch:
            return None
        if isinstance(I, ampy.types.BranchInstruction) and self.simple_branch:
            return sanitise(f"if ({I.cond})")
        return sanitise(repr(I))

    def tex_math(self, I):
        def reg(var):
            if not var.startswith('%'):
                return var
            # group letters into words
            # (but single letters will be left in "math mode")
            var = re.sub(r"([a-zA-Z][a-zA-Z0-9]+)", r"\\mathrm{\1}", var)
            # handle "anonymous" vars
            var = re.sub(r"%(\d)(.*)", r"\\varrho_{\1\2}", var)
            # treat '.' as an underscore
            # (but only if var is not anonymous)
            var = re.sub(r"%([^._]*)\.(.+)", r"{\1}_{\2}", var)
            # treat '_' as a different style underscore
            # (but only if there is no initial '.')
            var = re.sub(r"%([^._]*)_(.+)", r"{\1}_{(\2)}", var)
            # now handle remaining characters
            var = var.replace('.', ',').replace('%', '')
            var = re.sub(r"_(?!\{)", r'\\_', var)
            return var

        match type(I):
            case ampy.types.MovInstruction:
                return fr"{reg(I.target)} \gets {reg(I.operand)}"

            case ampy.types.PhiInstruction:
                if self.no_phi_labels:
                    args = ", ".join(reg(val) for val, _ in I.conds)
                else:
                    args = ", ".join(
                            fr"\overset{{{self.tex_label(cond)}}}{{\vphantom{{|}}{reg(val)}}}"
                            for val, cond in I.conds)
                return fr"{reg(I.target)} \gets \phi({args})"

            case T if issubclass(T, ampy.types.BinaryInstructionClass):
                op1, op2 = map(lambda o: re.sub(r"-(.*)", r"(-\1)", reg(o)),
                            I.operands)
                    
                if issubclass(T, ampy.types.ArithInstructionClass):
                    match I.op:
                        case '*':
                            op = r"\cdot"
                        case '/':
                            op = r"\div"
                        case '%':
                            op = r"\mod"
                        case _:
                            op = I.op

                elif issubclass(T, ampy.types.BitwiseInstructionClass):
                    match I.op:
                        case '&':
                            op = r"\wedge"
                        case '|':
                            op = r"\vee"
                        case '^':
                            op = r"\mathbin{\underline{\vee}}"
                            # or \oplus, I guess
                        case "<<":
                            op = r"\ll"
                        case ">>":
                            op = r"\gg"
                        case _:
                            op = I.op

                elif issubclass(T, ampy.types.CompInstructionClass):
                    match I.op:
                        case "==":
                            op = '='
                        case "!=":
                            op = r"\neq"
                        case "<=":
                            op = r"\leq"
                        case _:
                            op = I.op
                    # also override return in this case
                    return fr"{reg(I.target)} \gets ({op1} {op} {op2})"

                return fr"{reg(I.target)} \gets {op1} {op} {op2}"
            
            case ampy.types.GotoInstruction:
                if self.simple_branch:
                    return None
                return fr"\mathbf{{goto}}~{self.tex_label(I.target)}"

            case ampy.types.BranchInstruction:
                if self.simple_branch:
                    return fr"\mathbf{{if}}({reg(I.cond)})"
                return fr"\mathbf{{if}}({reg(I.cond)})~\mathbf{{goto}}~{self.tex_label(I.iftrue)} \\ \mathbf{{goto}}~{self.tex_label(I.iffalse)}"

            case ampy.types.ExitInstruction:
                return r"\mathbf{exit}"
            
            case ampy.types.ReadInstruction:
                return fr"{reg(I.target)} \gets \mathbf{{read}}()"

            case ampy.types.WriteInstruction:
                return fr"\mathbf{{write}}({reg(I.operand)})"

            case _:
                # ignore breakpoints and unknowns
                return None
