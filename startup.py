import subprocess
import sys
import os
import argparse
from scripts.init_infrastructure import init_elasticsearch_indices, start_debezium

def run_pipeline(args):
    print("[1/2] init infrastructure...")
    try:
        init_elasticsearch_indices(fresh_start=args.fresh)
        start_debezium()
    except Exception as e:
        print(f"Error during infrastructure init: {e}")
        sys.exit(1)

    print("[2/2] starting processor...")
    processor_path = os.path.join("scripts", "processor.py")
    
    try:
        process = subprocess.Popen(
            [sys.executable, "-u", processor_path],
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        print("Processor started. Ctrl+C to interrupt.\n")
        process.wait()
    except KeyboardInterrupt:
        print("\nInterrupting processor...")
        process.terminate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline infrastructure manager.")
    
    parser.add_argument(
        "--fresh", 
        action="store_true", 
        help="Clean existing data. Without this flag, it maintains existing data."
    )
    
    args = parser.parse_args()
    run_pipeline(args)