#!/usr/bin/env python3

import argparse


def _add_common_args(parser):
    """
    Common arguments shared by both:
      - run_ufs_workflow.py
      - build_rocotoxml.py
    """

    # ----------------------------------------------------------------------
    # Machine / account
    # ----------------------------------------------------------------------
    parser.add_argument(
        "-a", "--account",
        required=False,
        help="HPC account name"
    )
    parser.add_argument(
        "-m", "--machine",
        required=False,
        help="Machine ID (orion, hera, jet, derecho)"
    )

    # ----------------------------------------------------------------------
    # Test selection
    # ----------------------------------------------------------------------
    parser.add_argument(
        "-f", "--manifest",
        required=False,
        help="Path to app_manifest.yaml"
    )
    parser.add_argument(
        "-y", "--yamls_dir",
        required=False,
        default="tests-yamls/configs/by_app",
        help="Directory containing by_app YAMLs"
    )
    parser.add_argument(
        "-u", "--user-yaml",
        required=False,
        help="User-supplied test YAML"
    )
    parser.add_argument(
        "-n", "--single-test",
        required=False,
        help="Run a single test by ID"
    )
    parser.add_argument(
        "-l", "--test-list",
        required=False,
        help="Run tests listed in a file"
    )

    # ----------------------------------------------------------------------
    # Baseline / regression
    # ----------------------------------------------------------------------
    parser.add_argument(
        "-c", "--create-baseline",
        action="store_true",
        help="Create baseline outputs"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite of existing workflow XML"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing"
    )
    parser.add_argument(
        "--skip-check-results",
        action="store_true",
        help="Skip result comparison"
    )
    parser.add_argument(
        "--delete-rundir",
        action="store_true",
        help="Delete run directory after completion"
    )
    parser.add_argument(
        "--rt-suffix",
        required=False,
        default="",
        help="Suffix for regression test directory"
    )
    parser.add_argument(
        "--bl-suffix",
        required=False,
        default="",
        help="Suffix for baseline directory"
    )

    # User-specified baseline override
    parser.add_argument(
        "--users-baseline",
        required=False,
        help="Override NEW_BASELINE and RTPWD with a user-specified baseline directory"
    )

    # ----------------------------------------------------------------------
    # Verbosity
    # ----------------------------------------------------------------------
    parser.add_argument(
        "--rtverbose",
        action="store_true",
        help="Enable verbose regression test output"
    )

    # ----------------------------------------------------------------------
    # Runtime directory (bash-controlled)
    # ----------------------------------------------------------------------
    parser.add_argument(
        "--rundir-root",
        required=True,
        help="Runtime directory created by run_ufs_testsuite.sh"
    )

    return parser


def build_workflow_arg_parser():
    """
    Parser for run_ufs_workflow.py
    """
    parser = argparse.ArgumentParser(
        description="Unified UFS workflow runner (Sequential + Rocoto)"
    )

    # ------------------------------------------------------------------
    # Workflow mode
    # ------------------------------------------------------------------
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run workflow in sequential mode (no Rocoto)"
    )

    parser.add_argument(
        "-r", "--rocoto",
        action="store_true",
        help="Generate Rocoto XML"
    )

    parser.add_argument(
        "--run-rocoto",
        action="store_true",
        help="Submit workflow to Rocoto after generating XML"
    )

    parser.add_argument(
        "--monitor-rocoto",
        action="store_true",
        help="Monitor Rocoto workflow after submission"
    )

    # ------------------------------------------------------------------
    # Experiment identity
    # ------------------------------------------------------------------
    parser.add_argument(
        "--app",
        required=False,
        help="Application name"
    )
    parser.add_argument(
        "--expid",
        required=False,
        default="ufs_regression",
        help="Experiment ID"
    )

    # ------------------------------------------------------------------
    # Common args
    # ------------------------------------------------------------------
    _add_common_args(parser)
    return parser


def build_rocoto_arg_parser():
    """
    Parser for build_rocotoxml.py
    """
    parser = argparse.ArgumentParser(
        description="Generate Rocoto XML"
    )

    parser.add_argument(
        "--expid",
        required=False,
        default="ufs_regression",
        help="Experiment ID"
    )

    _add_common_args(parser)
    return parser
