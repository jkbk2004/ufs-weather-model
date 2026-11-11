"""rtlib: Python layer for the UFS Weather Model regression tests.

Built incrementally inside tests/ so that rt.sh keeps working at every step.

Step 1 (this package today): read rt.conf into a validated schema and
compute the ordered compile/run plan for a machine, exactly as rt.sh does.
Nothing here submits jobs or writes run directories.

Requires only the Python standard library (3.8+), so it runs with the
system/module python on every RDHPCS and WCOSS2 machine.
"""

__version__ = "0.1.0"
