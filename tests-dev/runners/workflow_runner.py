import argparse
from runners.rocoto_runner import RocotoRunner
# from runners.ecflow_runner import EcflowRunner  # future use

def main():
    parser = argparse.ArgumentParser(description="Run workflow tasks sequentially.")
    parser.add_argument("--backend", choices=["rocoto", "ecflow"], required=True)
    parser.add_argument("--file", required=True, help="Path to Rocoto XML or ecFlow .def file")
    args = parser.parse_args()

    if args.backend == "rocoto":
        runner = RocotoRunner(args.file)
    elif args.backend == "ecflow":
        raise NotImplementedError("ecFlow backend not yet implemented.")
    
    runner.run_sequentially()

if __name__ == "__main__":
    main()
