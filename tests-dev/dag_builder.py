"""
dag_builder.py

Build a simple dependency graph (DAG) from enriched test contexts.
Used by sequential execution.
"""

from collections import defaultdict, deque


class DagError(Exception):
    """Raised when the dependency graph is invalid (e.g., contains a cycle)."""
    pass


def build_dag(test_contexts):
    """
    Build a DAG from test_contexts.

    Parameters
    ----------
    test_contexts : dict[str, object]
        Mapping from test name/id to an object or dict that has at least:
        - "id" or name key
        - "dependency" and/or "parent" (optional)

    Returns
    -------
    dict[str, set[str]]
        A mapping: node -> set of dependency node names.
    """
    dag = {}

    for name, ctx in test_contexts.items():
        if isinstance(ctx, dict):
            parent = ctx.get("parent")
            dep = ctx.get("dependency")
        else:
            parent = getattr(ctx, "parent", None)
            dep = getattr(ctx, "dependency", None)

        deps = set()
        if parent:
            deps.add(parent)
        if dep:
            deps.add(dep)

        dag[name] = deps

    return dag


def topological_sort(dag):
    """
    Perform a topological sort on the DAG.

    Parameters
    ----------
    dag : dict[str, set[str]]
        Mapping: node -> set of dependencies.

    Returns
    -------
    list[str]
        Nodes in a valid topological order.

    Raises
    ------
    DagError
        If the graph contains a cycle.
    """
    children = defaultdict(set)
    indegree = {}

    for node, deps in dag.items():
        indegree[node] = len(deps)
        for d in deps:
            children[d].add(node)

    queue = deque([n for n, deg in indegree.items() if deg == 0])
    order = []

    while queue:
        n = queue.popleft()
        order.append(n)

        for c in children[n]:
            indegree[c] -= 1
            if indegree[c] == 0:
                queue.append(c)

    if len(order) != len(dag):
        raise DagError("Dependency graph contains a cycle")

    return order
