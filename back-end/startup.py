import subprocess
import sys
import os
import argparse
from pipeline.init_infrastructure import init_elasticsearch_indices, start_debezium, reset_kafka

def main(args):
    print("[1/2] Initializing streaming infrastructure...")
    try:
        reset_kafka(fresh_start=args.fresh) 
        init_elasticsearch_indices(fresh_start=args.fresh)
        start_debezium(fresh_start=args.fresh)   
    except Exception as e:
        print(f"[CRITICAL] Error during infrastructure initialization: {e}")
        sys.exit(1)

    print("[2/2] Starting real-time data processor...")
    processor_path = os.path.join("pipeline", "processor.py")
    
    if not os.path.exists(processor_path):
        print(f"[CRITICAL] Processor file not found at '{processor_path}'. Please check directory structure.")
        sys.exit(1)

    try:
        process = subprocess.Popen(
            [sys.executable, "-u", processor_path],
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        print("Real-time processor service started. Press Ctrl+C to interrupt.\n")
        process.wait()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupt received. Terminating processor process...")
        process.terminate()
        print("Processor stopped cleanly.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline architecture manager for Piedmont Tourism system.")
    
    parser.add_argument(
        "--fresh", 
        action="store_true", 
        help="Wipe and clean existing indexes in Elasticsearch. Default: maintain existing indices."
    )
    
    args = parser.parse_args()
    main(args)