"""
DJ Graph
==========
Goldthorpe

This module implements the DJ graph data structure that provides efficient
computations for iterated dominance frontiers and incremental dominator trees.
This is not an optimisation pass in itself.

V.C. Sreedhar, G.R. Gao. 1994.
    "Computing phi-nodes in Linear Time"
    POPL'95
    Pages 62--73.
V.C. Sreedhar, G.R. Gao, Y.F. Lee. 1997.
    "Incremental Computation of Dominator Trees"
    ACM Transactions on Programming Languages and Systems
    Vol. 19, No. 2.
    Pages 239--252.
"""

from utils.syntax import Syntax

from opt.analysis.domtree import DomTreeAnalysis
from opt.tools import RequiresOpt

import ampy.types

class DJGraph(RequiresOpt):
    """
    DJ graph from Sreedhar-Gao.

    Vertices are nodes in a CFG.
    D-edges are edges from the dominator tree of the CFG.
    J-edges are the edges B -> C of the CFG where B does not strictly dominate C
    """

    def __init__(self, cfg, opts):
        super().__init__(cfg, opts)
        self._create_D_edges()
        self._create_J_edges()

    @(Syntax(object) >> None)
    def _create_D_edges(self):
        domtree = self.require(DomTreeAnalysis)
        self._root = self.CFG.entrypoint
        self._D = {}
        self._level = {}
        self._up_dict = {} # data structure for least common ancestor
        self._up_valid = {} # for coherence of up_dict
        def dfs(node, level):
            self._level[node] = level
            self._D[node] = set()
            for child in domtree.children(node):
                dfs(child, level+1)
                self._D[node].add(child)
                self._up_dict[child, 0] = node
                self._up_valid[child] = 0 # to manage updates
        dfs(self._root, 0)

    @(Syntax(object) >> None)
    def _create_J_edges(self):
        self._J = {}
        for block in self.CFG.postorder: # restrict to reachable nodes
            self._J[block] = set()
            for child in block.children:
                if child == block or not self.dominates(block, child):
                    self._J[block].add(child)

    @(Syntax(object, (ampy.types.BasicBlock, None), int) >> (ampy.types.BasicBlock, None))
    def _up(self, block, e):
        """
        Returns the block (1<<e) steps up in the dominator tree.
        """
        if block is None or block == self._root:
            return None
        if (self._up_valid[block] < e or block, e) not in self._up_dict:
            if e == 0:
                # node is not in the dominator tree
                return None
            h = e - 1
            self._up_dict[block, e] = self._up(self._up(block, h), h)
            self._up_valid[block] = max(e, self._up_valid[block])
        return self._up_dict[block, e]


    @(Syntax(object, ampy.types.BasicBlock) >> (ampy.types.BasicBlock, None))
    def idom(self, block):
        """
        Return the immediate dominator of a block
        """
        return self._up(block, 0)

    @(Syntax(object, ampy.types.BasicBlock) >> [tuple, ampy.types.BasicBlock])
    def D_children(self, block):
        """
        Returns the children of block in the dominator tree
        """
        try:
            return tuple(self._D[block])
        except KeyError:
            return ()

    @(Syntax(object, ampy.types.BasicBlock, ampy.types.BasicBlock) >> (ampy.types.BasicBlock, None))
    def least_common_dominator(self, A, B):
        """
        Computes the least common ancestor of A and B in the dominator tree.
        Assumes both A and B are in the dominator tree to begin with (i.e., are
        reachable from the entrypoint).
        """
        if self._level[A] > self._level[B]:
            return self.least_common_dominator(B, A)
        
        diff = self._level[B] - self._level[A]
        count = 0
        while diff > 0:
            if diff & 1:
                B = self._up(B, count)
            diff >>= 1
            count += 1

        if A == B:
            return A

        count = 0
        level = self._level[B]
        while level > 0:
            count += 1
            level >>= 1

        while count >= 0:
            if self._up(A, count) == self._up(B, count):
                count -= 1
                continue

            # up[A, count+1] == up[B, count+1] but up[A, count] != up[B, count]
            A = self._up(A, count)
            B = self._up(B, count)

        # A != B is maintained in the above loop
        return self._up(A, 0)
    
    @(Syntax(object, ampy.types.BasicBlock, ampy.types.BasicBlock) >> bool)
    def dominates(self, A, B):
        """
        A faster test for if A dominates B.
        A dominates B iff A == LCD(A, B)
        """
        return A == self.least_common_dominator(A, B)

    @(Syntax(object, ampy.types.BasicBlock, ...) >> [set, ampy.types.BasicBlock])
    def dominance_frontier(self, *blocks):
        """
        The dominance frontier of a block B consists of all B' for which
        B dominates a parent of B', but does not strictly dominate B' itself.
        The dominance frontier of a set of blocks is the union of the DF of
        each block of the set.
        """
        if len(blocks) > 0:
            return self.dominance_frontier(blocks[0]) | self.dominance_frontier(*blocks[1:])
        if len(blocks) == 0:
            return set()
        block = blocks[0]
        if block not in self._level:
            return set()
        level = self._level[block]
        df = set()
        def dfs(node):
            for child in self._D[node]:
                for join in self._J[child]:
                    if self._level[join] <= level:
                        df.add(join)
        dfs(block)
        return df

    @(Syntax(object, ampy.types.BasicBlock, ..., _minlevel=int) >> [set, ampy.types.BasicBlock])
    def iterated_dominance_frontier(self, *blocks, _minlevel=0):
        """
        The iterated dominance frontier is the limit of S_n where
        S_0 is the input set of blocks, and
        S_{n+1} := DF[S_0 + S_n]

        The minimum level is for computing the subset of IDF consisting of
        nodes whose depth in the dominator tree is >= the minlevel
        """
        piggybank = {}
        self._cur_level = max(self._level.values())+1
        self._cur_root = None
        idf = set()
        blocks = set(blocks)
        visited = set()
        def insert(node):
            piggybank.setdefault(self._level[node], []).append(node)
        def get():
            level = self._cur_level
            while level > 0:
                ls = piggybank.get(level, [])
                if len(ls) > 0:
                    self._cur_level = level
                    return ls.pop()
                level -= 1
            return None # the piggybank is empty
        def visit(node):
            visited.add(node)
            for join in self._J[node]:
                if _minlevel <= self._level[join] <= self._level[self._cur_root]:
                    if join not in idf:
                        idf.add(join)
                        if join not in blocks:
                            insert(join)
            for dchild in self._D[node]:
                if dchild not in visited:
                    visit(dchild)

        # now to do the computation
        for block in blocks:
            insert(block)
        while (block := get()) is not None:
            self._cur_level = self._level[block]
            self._cur_root = block
            visit(block)

        return idf

    @(Syntax(object, ampy.types.BasicBlock, ampy.types.BasicBlock) >> None)
    def insert_edge(self, A, B):
        """
        Update the DJ-graph after inserting an edge between two nodes.
        The assumption is that at least A is already in the dominator tree.
        """
        if B not in self._D:
            # this node does not yet exist in the dominator
            # therefore, A is its immediate dominator
            self._D[A].add(B)
            self._D[B] = set()
            self._J[B] = set()
            self._level[B] = self._level[A] + 1
            self._up_dict[B, 0] = A
            self._up_valid[B] = 0

        lcd = self.least_common_dominator(A, B)
        if lcd != A:
            # if A dominates B already, then the dominator tree does not change
            # otherwise, we have inserted a J-edge
            if B in self._J[A]:
                # the J-edge is already present, so we can just quit
                return
            self._J[A].add(B)

        affected = self.iterated_dominance_frontier(B, _minlevel = self._level[lcd]+1)
        if self._level[B] > self._level[lcd] + 1:
            affected.add(B)

        def correct_level(node, level):
            self._level[node] = level
            self._up_valid[node] = 0 # invalidate the higher entries, if any
            for dtchild in self._D[node]:
                correct_level(dtchild, level+1)

        for block in affected:
            # the entrypoint will never be in affected
            # because of the level requirement
            idom = self.idom(block)
            self._D[idom].remove(block)
            if block in idom.children:
                self._J[idom].add(block)

            self._D[lcd].add(block)
            self._up_dict[block, 0] = lcd
            correct_level(block, self._level[lcd]+1)

