"""Machines rt.sh knows about.

Step 1 only needs the names (for validation). Step 2 moves the per-machine
settings from rt.sh's `case ${MACHINE_ID}` block into machines.yaml and
this module will load them.
"""

# Every MACHINE_ID handled by rt.sh's case block.
KNOWN_MACHINES = (
    "acorn",
    "wcoss2",
    "gaeac5",
    "gaeac6",
    "hera",
    "ursa",
    "orion",
    "hercules",
    "derecho",
    "noaacloud",
)
