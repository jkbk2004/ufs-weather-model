#!/usr/bin/env python3

from pathlib import Path
from jinja2 import Environment, FileSystemLoader


def write_rocotoxml_from_ctx(ctx):
    """
    Render Rocoto XML from Jinja2 template using the prepared context.
    Template must be located at:
        <PATHRT>/templates/rocoto_workflow.j2
    """

    # ------------------------------------------------------------------
    # Template directory and file
    # ------------------------------------------------------------------
    template_dir = Path(ctx.pathrt) / "templates"
    template_name = "rocoto_workflow.j2"

    template_path = template_dir / template_name
    if not template_path.exists():
        raise FileNotFoundError(
            f"Template not found: {template_path}\n"
            f"Expected template directory: {template_dir}"
        )

    # ------------------------------------------------------------------
    # Jinja environment
    # ------------------------------------------------------------------
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    template = env.get_template(template_name)

    # ------------------------------------------------------------------
    # Normalize tests into simple objects for Jinja
    # ------------------------------------------------------------------
    tests = []
    for t in ctx.tests:
        tests.append(
            type(
                "Test",
                (),
                {
                    "id": t["id"],
                    "type": t["type"],
                    "parent": t.get("parent"),
                    "dependency": t.get("dependency") or "",
                    "option": t.get("option", ""),
                    "nodes": t.get("nodes", ""),
                    "walltime": t.get("walltime", ""),
                },
            )()
        )

    # ------------------------------------------------------------------
    # Render XML text
    # ------------------------------------------------------------------
    xml_text = template.render(
        PATHRT=ctx.pathrt,
        LOG=ctx.logdir,
        PATHTR=ctx.patht,
        RTPWD=ctx.rtpwd,
        INPUTDATA_ROOT=ctx.inputdata_root,
        INPUTDATA_ROOT_WW3=ctx.inputdata_root_ww3,
        INPUTDATA_ROOT_BMIC=ctx.inputdata_root_bmic,
        INPUTDATA_ROOT_LM4=ctx.inputdata_root_lm4,
        RUNDIR_ROOT=ctx.rundir_root,
        NEW_BASELINE=ctx.new_baseline,

        # Scheduler + resources
        scheduler=ctx.machine_config.get("SCHEDULER", "slurm"),
        queue=ctx.machine_config.get("QUEUE", "batch"),
        account=ctx.machine_config.get("ACCOUNT", "epic"),
        partition=ctx.machine_config.get("PARTITION", "orion"),

        # Tests
        tests=tests,
    )

    # ------------------------------------------------------------------
    # Write XML to file
    # ------------------------------------------------------------------
    xml_path = Path(ctx.pathrt) / f"{ctx.expid}.xml"
    xml_path.write_text(xml_text + "\n")

    print(f"[INFO] Rocoto XML written to {xml_path}")
