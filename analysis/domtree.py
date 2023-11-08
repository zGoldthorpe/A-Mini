"""
Dominator tree
================
Goldthorpe

This module provides an analysis class for computing
the dominator tree of the given CFG.

The algorithm used is that of the paper

T. Lengauer, R.E. Tarjan. 1979.
    "A Fast Algorithm for Finding Dominators in a Flowgraph"
    ACM Transactions on Programming Languages and Systems
    Vol. 1, No. 1.
    Pages 121--141.
"""

from ampy.ensuretypes import Syntax
from analysis.tools import Analysis

import ampy.types

class DomTreeAnalysis(Analysis):
    # forward declaration
    pass

class DomTreeAnalysis(DomTreeAnalysis):
    """
    domtree

    Runs the Lengauer-Tarjan algorithm for computing the dominator
    tree for a control flow graph.
    """

    @DomTreeAnalysis.init("domtree")
    def __init__(self, /):
        pass

    @DomTreeAnalysis.getter
    @(Syntax(object, ampy.types.BasicBlock, ampy.types.BasicBlock) >> bool)
    def dominates(self, A, B):
        """
        Determines if the block A dominates the block B
        """
        while True:
            if B == A:
                return True
            ls = self[B:"idom"]
            if ls is None or len(ls) == 0:
                return False
            B = self.CFG[ls[0]]

    @DomTreeAnalysis.analysis
    def lengauer_tarjan(self):
        """
        Lengauer-Tarjan dominator tree constructor
        """
        self.clear() # clear metadata prior to running analysis

        # Step 1. DFS
        # -----------
        # semi[B]: gives the DFS index of the block B
        # vertex[i]: gives the block with DFS index i
        # dfs_parent[B]: parent block in DFS tree
        self._semi = {
                block : -1
                for block in self.CFG
                }
        self._vertex = []
        self._dfs_parent = {
                block : None
                for block in self.CFG
                }
        self._DFS(self.CFG.entrypoint)

        # Step 2. Semidominators
        # Step 3. Implicit immediate dominators
        # -------------------------------------
        # The semidominator of a vertex w is the vertex v with
        # minimal DFS index with the property that there is a path
        # v -> w consisting of vertices of DFS index strictly
        # greater than that of w
        #
        # semi[B]: DFS index of the semidominator of B
        # bucket[B]: set of blocks whose semidominator is B
        # idom[B]: semi[B] if this is the immediate dominator of B
        #          otherwise, is a block of smaller DFS index whose
        #          immediate dominator is also that of B
        #          (is None if B is the entry point, or is unreachable)
        #
        # LINK(B, B'): link B and B' in processed subforest of DFS tree
        # EVAL(B): if B is the root of its tree in this forest, return B
        #          otherwise, return any non-root vertex of minimum semi[-]
        #          on the path from the root to B
        # ancestor[B]: ancestor of B in forest (or None if N/A)
        # label[B]: identifiers of B such that minimality along a path from
        #           root to B can be tested on just the labels
        # size[B]: necessary for maintaining tree balance
        # child[B]: likewise for maintaining tree balance
        self._bucket = {
                block : set()
                for block in self.CFG
                }
        self._ancestor = {
                block : None
                for block in self.CFG
                }
        self._label = {
                block : block
                for block in self.CFG
                }
        self._child = {
                block : -1
                for block in self.CFG
                }
        self._size = {
                block : 1
                for block in self.CFG
                }
        self._idom = {
                block : None
                for block in self.CFG
                }

        self._semi[-1] = -1
        self._label[-1] = -1
        self._size[-1] = 0 # edge case definitions for convenience in LINK

        for i in range(len(self._vertex)-1, 0, -1):
            block = self._vertex[i]
            # process blocks in reverse order by DFS index
            # excluding the root
            for parent in block.parents:
                minsemi = self._eval(parent)
                self._semi[block] = min(self._semi[block], self._semi[minsemi])

            # add block to the bucket of its semidominator
            self._bucket[self._vertex[self._semi[block]]].add(block)
            dfs_parent = self._dfs_parent[block]
            self._link(dfs_parent, block)

            # now find immediate dominators
            while len(self._bucket[dfs_parent]) > 0:
                sdom = self._bucket[dfs_parent].pop()
                minsemi = self._eval(sdom)
                if self._semi[minsemi] < self._semi[sdom]:
                    self._idom[sdom] = minsemi
                else:
                    self._idom[sdom] = dfs_parent
        
        # Step 4. Immediate dominators
        # ----------------------------
        for i in range(1, len(self._vertex)):
            block = self._vertex[i]
            if self._idom[block] != self._vertex[self._semi[block]]:
                self._idom[block] = self._idom[self._idom[block]]

        # now, push information to CFG metadata
        for block in self.CFG:
            if self._idom[block] is None:
                self.assign(block, "idom")
            else:
                self.assign(block, "idom", self._idom[block].label)
                self.assign(self._idom[block], "children", block.label, append=True)

    @(Syntax(object, ampy.types.BasicBlock) >> None)
    def _DFS(self, block):
        """
        Performs DFS and stores counter to visited blocks
        """
        self._semi[block] = len(self._vertex)
        self._vertex.append(block)

        for child in block.children:
            if self._semi[child] > -1:
                continue
            self._dfs_parent[child] = block
            self._DFS(child)

    @(Syntax(object, ampy.types.BasicBlock, ampy.types.BasicBlock) >> None)
    def _link(self, src, tgt):
        block = tgt
        while self._semi[self._label[block]] < self._semi[self._label[self._child[block]]]:
            # rebalance tree
            if self._size[block] + self._size[self._child[self._child[block]]] >= 2*self._size[self._child[block]]:
                self._dfs_parent[self._child[block]] = block
                self._child[block] = self._child[self._child[block]]
            else:
                self._dfs_parent[block] = self._child[block]
                s = self._dfs_parent[block]

        self._label[block] = self._label[tgt]
        self._size[src] += self._size[tgt]
        if self._size[src] <= 2*self._size[tgt]:
            (block, self._child[block]) = (self._child[block], block)
        while isinstance(block, ampy.types.BasicBlock):
            self._dfs_parent[block] = src
            block = self._child[block]

    @(Syntax(object, ampy.types.BasicBlock) >> ampy.types.BasicBlock)
    def _eval(self, block):
        """
        EVAL(B): if B is the root of its tree in this forest, return B
                 otherwise, return any non-root vertex of minimum semi[-]
                 on the path from the root to B
        """
        if self._ancestor[block] is None:
            return self._label[block]
        self._compress(block)
        return (self._label[block]
                if self._semi[self._label[self._ancestor[block]]]
                    >= self._semi[self._label[block]]
                else self._label[self._ancestor[block]])

    @(Syntax(object, ampy.types.BasicBlock) >> None)
    def _compress(self, block):
        """
        Performs path compression in the tree containing block
        Assumes self._ancestor[block] is not None
        """
        if self._ancestor[self._ancestor[block]] is not None:
            self._compress(self._ancestor[block])
            if self._semi[self._label[self._ancestor[block]]] < self._semi[self._label[block]]:
                self._label[block] = self._label[self._ancestor[block]]

            self._ancestor[block] = self._ancestor[self._ancestor[block]]

