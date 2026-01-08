"""
dag_builder.py

Builds a directed acyclic graph (DAG) of test dependencies for the UFS
regression workflow. This module is intentionally pure: it does not touch
the filesystem, environment variables, or machine configuration.

It takes a list of test dictionaries (from TestLoader) and returns
a dependency graph that can be consumed by:

  - sequential_executor.py
  - build_rocotoxml.py
  - future SLURM/PBS adapters
  - CI/CD runners

This ensures a single source of truth for workflow structure.
"""

from __future__ import annotations
from typing import List, Dict, Any
import networkx as nx


class DAGBuilder:
    """
    Build a dependency graph from a list of test dictionaries.

    Each test dictionary is expected to have:
        - id: str
        - type: "compile" or "run"
        - parent: str or None
        - dependency: str or None
        - any other metadata needed by executors
    """

    def __init__(self, tests: List[Dict[str, Any]]):
        self.tests = tests
        self.graph = nx.DiGraph()

        # Map test_id → test_dict
        self.test_map = {t["id"]: t for t in tests}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def build(self) -> nx.DiGraph:
        """Build and return a directed acyclic graph (DAG)."""
        self._add_nodes()
        self._add_edges()
        self._validate_acyclic()
        return self.graph

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _add_nodes(self):
        """Add all tests as nodes."""
        for t in self.tests:
            self.graph.add_node(t["id"], test=t)

    def _add_edges(self):
        """
        Add dependency edges.

        Supported dependency sources:
          1. Explicit dependency:   t["dependency"]
          2. Parent/child mapping:  run test depends on its compile parent
        """
        for t in self.tests:
            tid = t["id"]

            # ----------------------------------------------------------
            # 1. Explicit dependency
            # ----------------------------------------------------------
            dep = t.get("dependency")
            if dep:
                if dep not in self.test_map:
                    raise ValueError(
                        f"Test '{tid}' depends on unknown test '{dep}'"
                    )
                self.graph.add_edge(dep, tid)

            # ----------------------------------------------------------
            # 2. Parent → child (compile → run)
            # ----------------------------------------------------------
            parent = t.get("parent")
            if parent:
                if parent not in self.test_map:
                    raise ValueError(
                        f"Test '{tid}' has unknown parent '{parent}'"
                    )
                self.graph.add_edge(parent, tid)

    def _validate_acyclic(self):
        """Ensure the graph is acyclic."""
        if not nx.is_directed_acyclic_graph(self.graph):
            cycle = nx.find_cycle(self.graph)
            raise ValueError(f"Dependency cycle detected: {cycle}")


# ----------------------------------------------------------------------
# Convenience function
# ----------------------------------------------------------------------
def build_dag(tests: List[Dict[str, Any]]) -> nx.DiGraph:
    """Build a DAG from a list of test dictionaries."""
    return DAGBuilder(tests).build()
