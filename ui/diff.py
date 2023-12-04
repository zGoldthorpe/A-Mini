"""
File differences
==================
Goldthorpe
"""

import utils.debug
import utils.printing

from ui.errors import perror, die, unexpected

class DiffUI:

    @classmethod
    def add_arguments(cls, parser):
        
        parser.add_argument("-w", "--width",
                        dest="DUIwidth",
                        metavar="WIDTH",
                        type=int,
                        default=48,
                        help="Set the width of one diff \"page\" (default 48).")
        parser.add_argument("-a", "--show-all",
                        dest="DUIall",
                        action="store_true",
                        help="Display the contents of both files lined up, rather than isolating just the lines around differences.")

    @classmethod
    def arg_init(cls, parsed_args):
        return cls(width=parsed_args.DUIwidth,
                fullcontent=parsed_args.DUIall)

    def __init__(self, width=48, fullcontent=False):
        self._width = width
        self._all = fullcontent
        if self._width <= 0:
            die("Diff page width cannot be zero.")
    
    def _rpkg(self, line):
        return tuple(filter(lambda m: len(m) > 0,
                (line[i*self._width:(i+1)*self._width]
                for i in range(1+len(line)//self._width))))
    def repackage(self, file):
        """
        Store file contents into a tuple of tuples of strings.
        Each tuple of strings corresponds to a single line of the file, but
        the line of the file is split into chunks of a fixed maximum width.
        """
        try:
            with open(file, 'r') as f:
                return tuple(self._rpkg(line)
                        for line in f.read().splitlines())
        except FileNotFoundError:
            die(f"{file} does not exist.")
        except Exception as e:
            unexpected(e)

    def read_files(self, left, right):
        """
        Read in the two files to diff.
        """
        self._left_fname = left
        self._right_fname = right
        self._left = self.repackage(left)
        self._right = self.repackage(right)

    @property
    def files_differ(self):
        """
        Return whether or not the file contents do indeed differ.
        """
        return self._left != self._right

    def display_diff(self):
        """
        After the two files are loaded, this prints the differences
        """
        lmask, rmask = self.dyn_diff()
        full_output = [] # aligned list of pairs (left, right)
        mistakes = set() # set of indices of full_output that mismatch
        lhs = []
        rhs = []
        li = 0
        ri = 0
        while li < len(lmask) and ri < len(rmask):
            if lmask[li]:
                while self._right[ri] != self._left[li]:
                    mistakes.add(len(full_output))
                    lhs.append('')
                    rhs.append(ri)
                    full_output.append(((), self._right[ri]))
                    ri += 1
            if rmask[ri]:
                while self._left[li] !=self._right[ri]:
                    mistakes.add(len(full_output))
                    lhs.append(li)
                    rhs.append('')
                    full_output.append((self._left[li], ()))
                    li += 1
            # either both are true, or both are false
            if not lmask[li]:
                mistakes.add(len(full_output))
            full_output.append((self._left[li], self._right[ri]))
            lhs.append(li)
            rhs.append(ri)
            li += 1
            ri += 1
        for i in range(li, len(lmask)):
            mistakes.add(len(full_output))
            lhs.append(i)
            rhs.append('')
            full_output.append((self._left[i], ()))
        for i in range(ri, len(rmask)):
            mistakes.add(len(full_output))
            lhs.append('')
            rhs.append(i)
            full_output.append(((), self._right[i]))

        if len(mistakes) == 0:
            utils.debug.print("No differences detected.")
            return
       
        # context for the diff, for readability
        context = {i for i in range(len(full_output))
                if i+1 in mistakes or i in mistakes or i-1 in mistakes}
        to_print = {i for i in range(len(full_output))
                if ((i+1 in context and i-1 in context) or i in context)
                    or self._all}

        lpadding = len(str(li))
        rpadding = len(str(ri))

        # now, we can print the diff pages
        # first, the filenames
        utils.printing.psubtle(' '*lpadding, '+-' + '-'*self._width + '-+-'
                                + '-'*self._width + '-+')
        self.print_row(' '*lpadding, self._rpkg(self._left_fname),
                       ' '*rpadding, self._rpkg(self._right_fname),
                       wrong=False)
        utils.printing.psubtle('-'*lpadding, '+-' + '-'*self._width + '-+-'
                                + '-'*self._width + '-+', '-'*rpadding)
        prev_idx = -1
        
        for i in sorted(to_print):
            if i > prev_idx + 1:
                utils.printing.psubtle(' '*lpadding, ': '
                                        + ' '*self._width + ' : '
                                        + ' '*self._width + ' :')
            self.print_row(f"{lhs[i]: <{lpadding}}", full_output[i][0],
                           f"{rhs[i]: >{rpadding}}", full_output[i][1],
                            wrong=i in mistakes)
            prev_idx = i

        if i + 1 < len(full_output):
            utils.printing.psubtle(' '*lpadding, ': '
                                    + ' '*self._width + ' : '
                                    + ' '*self._width + ' :')

        utils.printing.psubtle('-'*lpadding, '+-' + '-'*self._width + '-+-'
                                + '-'*self._width + '-+', '-'*rpadding)

    def fit_to_line(self, s):
        """
        Fit `s` to a single line.
        """
        if len(s) > self._width:
            if self._width < 4:
                s = s[:self._width]
            else:
                s = s[:self._width-3]+"..."
        return f"{s: ^{self._width}}"

    def print_row(self, lline, lhs, rline, rhs, *, wrong):
        maxlen = max(len(lhs), len(rhs))
        lhs = tuple(lhs[i] if i < len(lhs) else None for i in range(maxlen))
        rhs = tuple(rhs[i] if i < len(rhs) else None for i in range(maxlen))
        for l, r in zip(lhs, rhs):
            self._print_line(lline, l, rline, r, wrong=wrong)
            lline = ' '*len(lline)
            rline = ' '*len(rline)
    
    def _print_line(self, lline, lhs, rline, rhs, *, wrong):
        utils.printing.psubtle(lline, '|',  end='')
        if lhs is None:
            utils.printing.phidden(':' + ' '*self._width + ':', end='')
        elif wrong:
            lhs = f" {lhs: <{self._width}} "
            utils.printing.perror(lhs, end='')
        else:
            lhs = f" {lhs: <{self._width}} "
            utils.printing.psubtle(lhs, end='')

        utils.printing.psubtle('|', end='')

        if rhs is None:
            utils.printing.phidden(':' + ' '*self._width + ':', end='')
        elif wrong:
            rhs = f" {rhs: <{self._width}} "
            utils.printing.perror(rhs, end='')
        else:
            rhs = f" {rhs: <{self._width}} "
            utils.printing.psubtle(rhs, end='')
        utils.printing.psubtle('|', rline)


    def dyn_diff(self):
        """
        After the two files are read, compute their difference.

        Match is encoded as a pair of lists lmask, rmask
        where lmask[i] is a list of bits indicating if the jth character
        of line i of the left file gets matched on the right, and vice versa
        for rmask.
        """
        table = [[None]*(len(self._right)+1) for _ in range(len(self._left)+1)]
        stack = [(0, 0)] # emulate recursion

        while len(stack) > 0:
            li, ri = stack.pop()
            if table[li][ri] is None:
                if li == len(self._left) or ri == len(self._right):
                    table[li][ri] = 0
                    continue
                if table[li][ri+1] is None:
                    stack.append((li, ri))
                    stack.append((li, ri+1))
                    continue
                if table[li+1][ri] is None:
                    stack.append((li, ri))
                    stack.append((li+1, ri))
                    continue
                if table[li+1][ri+1] is None:
                    stack.append((li, ri))
                    stack.append((li+1, ri+1))
                    continue
                table[li][ri] = max(
                        table[li][ri+1], # discard self._right char
                        table[li+1][ri], # discard self._left char
                        table[li+1][ri+1] + int(self._left[li] == self._right[ri]))

        # now that the best score is known, build the match
        score = table[0][0]
        rescore = 0
        lmask = [False]*len(self._left)
        rmask = [False]*len(self._right)
        li = 0
        ri = 0
        while li < len(lmask) and ri < len(rmask):
            if self._left[li] == self._right[ri]:
                lmask[li] = True
                rmask[ri] = True
                li += 1
                ri += 1
                rescore += 1
                continue
            if rescore + table[li+1][ri] == score:
                li += 1
                continue
            ri += 1
        return lmask, rmask
