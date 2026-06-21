import subprocess
import sys
import os
import argparse
from pipeline.init_infrastructure import init_elasticsearch_indices, start_debezium, reset_kafka, reset_neo4j


def main(args):
    print("[1/2] Initializing streaming infrastructure...")
    try:
        reset_kafka(fresh_start=args.fresh) 
        reset_neo4j(fresh_start=args.fresh)
        init_elasticsearch_indices(fresh_start=args.fresh)
        start_debezium(fresh_start=args.fresh)   
    except Exception as e:
        print(f"[CRITICAL] Error during infrastructure initialization: {e}")
        sys.exit(1)

    print("[2/2] Starting dual real-time data processors (ELK + Neo4j)...")
    processor_elk = os.path.join("pipeline", "processor_elk.py")
    processor_neo4j = os.path.join("pipeline", "processor_neo4j.py")
    
    processes = []
    try:
        p_elk = subprocess.Popen(
            [sys.executable, "-u", processor_elk],
            stdout=sys.stdout, stderr=sys.stderr
        )
        processes.append(p_elk)
        print("[INFO] Elasticsearch real-time indexer service triggered.")

        p_neo4j = subprocess.Popen(
            [sys.executable, "-u", processor_neo4j],
            stdout=sys.stdout, stderr=sys.stderr
        )
        processes.append(p_neo4j)
        print("[INFO] Neo4j spatial graph indexer service triggered.")
        
        print("Both decoupled synchronization engines are active. Press Ctrl+C to terminate.\n")
        
        p_elk.wait()
        p_neo4j.wait()

    except KeyboardInterrupt:
        print("\n[INFO] Termination signal received. Stopping both consumer groups cleanly...")
        for p in processes:
            p.terminate()
            p.wait()
        print("[SUCCESS] All pipeline workers stopped successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline architecture manager for Piedmont Tourism system.")
    
    parser.add_argument(
        "--fresh", 
        action="store_true", 
        help="Wipe and clean existing indexes in Elasticsearch. Default: maintain existing indices."
    )
    
    args = parser.parse_args()
    main(args)