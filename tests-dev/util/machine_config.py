from pathlib import Path
import yaml


REQUIRED_TOP_LEVEL_KEYS = [
    "ROCOTO_PATHS",
    "BASELINE_PATH",
    "RUNDIR_PATH",
    "INPUTDATA_ROOT",
]

REQUIRED_ROCOTO_KEYS = [
    "ROCOTORUN",
    "ROCOTOSTAT",
    "ROCOTOCOMPLETE",
]


def load_machine_config(machine_id: str) -> dict:
    """
    Load and validate machine-specific configuration from:
        tests-dev/machine_config/runtime_config_<machine>.yaml

    Ensures required fields exist and normalizes optional ones.
    """

    config_dir = Path(__file__).parent.parent / "machine_config"
    config_file = config_dir / f"runtime_config_{machine_id}.yaml"

    if not config_file.exists():
        raise FileNotFoundError(
            f"Machine config not found: {config_file}. "
            f"Expected runtime_config_{machine_id}.yaml"
        )

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Machine config {config_file} must contain a YAML mapping")

    # --------------------------------------------------------------------------
    # Validate required top-level keys
    # --------------------------------------------------------------------------
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in config:
            raise KeyError(
                f"Missing required key '{key}' in {config_file}. "
                f"Your workflow expects this field."
            )

    # --------------------------------------------------------------------------
    # Validate ROCOTO_PATHS block
    # --------------------------------------------------------------------------
    rocoto_paths = config.get("ROCOTO_PATHS", {})
    if not isinstance(rocoto_paths, dict):
        raise ValueError(f"ROCOTO_PATHS must be a mapping in {config_file}")

    for key in REQUIRED_ROCOTO_KEYS:
        if key not in rocoto_paths:
            raise KeyError(
                f"Missing ROCOTO_PATHS['{key}'] in {config_file}. "
                f"Your workflow requires this path."
            )

    # --------------------------------------------------------------------------
    # Optional fields with defaults
    # --------------------------------------------------------------------------
    config.setdefault("INPUTDATA_ROOT_WW3", "/inputdata_ww3")
    config.setdefault("INPUTDATA_ROOT_BMIC", "/inputdata_bmic")
    config.setdefault("INPUTDATA_LM4", "/inputdata_lm4")
    config.setdefault("QUEUE", "batch")
    config.setdefault("ACCOUNT", None)
    config.setdefault("MODULE_COMMANDS", [])

    # Ensure ROCOTO_PATHS is preserved
    config["ROCOTO_PATHS"] = rocoto_paths

    return config
