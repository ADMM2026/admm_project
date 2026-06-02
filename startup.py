import subprocess
import sys
import os
import time

def run_pipeline():
    sys.path.append(os.path.abspath(os.path.dirname(__file__)))
    print("[1/2] init infrastrucutre...")
    try:
        from scripts.init_infrastructure import init_elasticsearch_indices, start_debezium
        
        init_elasticsearch_indices()
        
        start_debezium()
    except Exception as e:
        print(e)
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
        print("\nInterrputing processor...")
        process.terminate()

if __name__ == "__main__":
    run_pipeline()