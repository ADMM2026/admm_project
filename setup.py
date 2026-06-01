#!/usr/bin/env python3
"""
setup.py – Orchestratore pipeline MongoDB → Kafka → Elasticsearch

Uso:
    python setup.py                  # avvio completo
    python setup.py --skip-compose   # salta docker compose up (già avviato)
    python setup.py --skip-seed      # salta il seeding MongoDB (dati già presenti)
    python setup.py --reset          # cancella indici ES e connettori prima di ricominciare
"""

import argparse
import json
import os
import subprocess
import sys
import time

from pymongo import MongoClient

import requests

# ─── Colori ANSI ──────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"{GREEN}  ✔  {msg}{RESET}")
def warn(msg):  print(f"{YELLOW}  ⚠  {msg}{RESET}")
def err(msg):   print(f"{RED}  ✖  {msg}{RESET}")
def info(msg):  print(f"{CYAN}  ▸  {msg}{RESET}")
def step(msg):  print(f"\n{BOLD}{CYAN}══ {msg} ══{RESET}")

# ─── Configurazione ────────────────────────────────────────────────────────────

CONNECT_URL  = "http://localhost:8083"
ES_URL       = "http://localhost:9200"
MONGO_URI    = "mongodb://localhost:27017/?directConnection=true"
MONGO_DB     = "tourism"   # nome target; rilevato case-insensitive se già esiste

CONNECTORS_DIR  = os.path.join(os.path.dirname(__file__), "connectors")
ES_MAPPINGS_DIR = os.path.join(os.path.dirname(__file__), "es_mappings")
SEEDERS_DIR     = os.path.join(os.path.dirname(__file__), "seeders")

ES_INDICES = {
    "accomodations": os.path.join(ES_MAPPINGS_DIR, "accomodations.json"),
    "attractions":   os.path.join(ES_MAPPINGS_DIR, "attractions.json"),
}

# ─── Helper HTTP ───────────────────────────────────────────────────────────────

def _get(url, **kwargs):
    try:
        return requests.get(url, timeout=5, **kwargs)
    except requests.RequestException:
        return None


def _put(url, payload, **kwargs):
    try:
        return requests.put(url, json=payload, timeout=30,
                            headers={"Content-Type": "application/json"}, **kwargs)
    except requests.RequestException:
        return None


def _post(url, payload, **kwargs):
    return requests.post(url, json=payload, timeout=10,
                         headers={"Content-Type": "application/json"}, **kwargs)


def _delete(url, **kwargs):
    try:
        return requests.delete(url, timeout=30, **kwargs)
    except requests.RequestException:
        return None

# ─── Health checks ─────────────────────────────────────────────────────────────

def wait_for_service(name: str, url: str, retries: int = 40, delay: int = 5):
    info(f"Waiting for {name} at {url}...")
    for attempt in range(1, retries + 1):
        r = _get(url)
        if r is not None and r.status_code < 500:
            ok(f"{name} is ready.")
            return True
        print(f"    attempt {attempt}/{retries}...", end="\r", flush=True)
        time.sleep(delay)
    err(f"{name} did not become ready after {retries * delay}s.")
    return False


def wait_for_kafka_connect(retries: int = 60, delay: int = 5) -> bool:
    """
    Attende che Kafka Connect sia veramente pronto:
    1. REST API risponde a /connectors
    2. Tutti i connettori già presenti sono in stato RUNNING (niente rebalancing)
    """
    info(f"Waiting for Kafka Connect at {CONNECT_URL}...")
    api_ready = False
    for attempt in range(1, retries + 1):
        r = _get(f"{CONNECT_URL}/connectors")
        if r is not None and r.status_code == 200:
            if not api_ready:
                api_ready = True
                info("  REST API up, waiting for connectors to stabilise...")
            # Controlla che tutti i connettori esistenti siano in RUNNING
            r2 = _get(f"{CONNECT_URL}/connectors?expand=status")
            if r2 and r2.status_code == 200:
                statuses = r2.json()
                if not statuses:  # nessun connettore → pronto subito
                    ok("Kafka Connect is ready (no existing connectors).")
                    return True
                all_running = all(
                    d.get("status", {}).get("connector", {}).get("state") == "RUNNING"
                    for d in statuses.values()
                )
                if all_running:
                    ok("Kafka Connect is ready (all connectors RUNNING).")
                    return True
        print(f"    attempt {attempt}/{retries}...", end="\r", flush=True)
        time.sleep(delay)
    err("Kafka Connect did not become fully ready.")
    return False

# ─── Docker Compose ────────────────────────────────────────────────────────────

def compose_up():
    step("Starting Docker Compose")
    result = subprocess.run(
        ["docker", "compose", "up", "-d", "--build"],
        cwd=os.path.dirname(__file__),
    )
    if result.returncode != 0:
        err("docker compose up failed.")
        sys.exit(1)
    ok("Containers started.")


def drop_mongo_db():
    """
    Rimuove il database MongoDB (case-insensitive) per permettere
    la ricreazione con il case corretto.
    """
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        existing = client.list_database_names()
        target = next((d for d in existing if d.lower() == MONGO_DB.lower()), None)
        if target:
            client.drop_database(target)
            ok(f"MongoDB database '{target}' dropped (reset).")
        else:
            info(f"MongoDB database '{MONGO_DB}' not found, nothing to drop.")
        client.close()
    except Exception as exc:
        warn(f"Could not drop MongoDB database: {exc}")

# ─── Seeding MongoDB ───────────────────────────────────────────────────────────

def _resolve_mongo_db_name() -> str:
    """
    Ritorna il nome esatto del database come esiste su MongoDB
    (risolve il case mismatch). Se non esiste ancora usa MONGO_DB.
    """
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        existing = client.list_database_names()
        client.close()
        match = next((d for d in existing if d.lower() == MONGO_DB.lower()), None)
        return match if match else MONGO_DB
    except Exception:
        return MONGO_DB


def run_seeders():
    step("Seeding MongoDB")

    # Aggiungiamo la root del progetto al path così gli import relativi funzionano
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    db_name = _resolve_mongo_db_name()
    info(f"Using MongoDB database: '{db_name}'")

    # ── Accomodations ──
    info("Running seed_accomodations...")
    try:
        from seeders.seed_accomodations import main as seed_acc
        import argparse as _ap

        acc_raw = os.path.join(SEEDERS_DIR, "raw_data")

        acc_args = _ap.Namespace(
            mongo_uri   = MONGO_URI,
            mongo_db    = db_name,
            locations   = os.path.join(acc_raw, "accomodations", "villeggiatura_losir.csv"),
            details     = os.path.join(acc_raw, "accomodations", "offerta_ricettiva_comuni.csv"),
            municipalities = os.path.join(acc_raw, "municipalities", "Com01012026_g_WGS84.shp"),
            output_json = os.path.join(SEEDERS_DIR, "data", "accommodations_backup.json"),
        )
        seed_acc(acc_args)
        ok("Accomodations seeded.")
    except Exception as exc:
        warn(f"Accomodations seeder failed: {exc}")

    # ── Attractions ──
    info("Running seed_attractions...")
    try:
        from seeders.seed_attractions import main as seed_att

        att_raw  = os.path.join(SEEDERS_DIR, "raw_data")
        att_args = _ap.Namespace(
            mongo_uri       = MONGO_URI,
            mongo_db        = db_name,
            attractions_dir = os.path.join(att_raw, "attractions"),
            municipalities  = os.path.join(att_raw, "municipalities", "Com01012026_g_WGS84.shp"),
            images_dir      = os.path.join(SEEDERS_DIR, "img"),
            output_json     = os.path.join(SEEDERS_DIR, "data", "attractions_backup.json"),
        )
        seed_att(att_args)
        ok("Attractions seeded.")
    except Exception as exc:
        warn(f"Attractions seeder failed: {exc}")

# ─── Elasticsearch – indici e mapping ─────────────────────────────────────────

def setup_es_indices(reset: bool = False):
    step("Setting up Elasticsearch indices")

    for index_name, mapping_file in ES_INDICES.items():
        index_url = f"{ES_URL}/{index_name}"

        if reset:
            r = _delete(index_url)
            if r and r.status_code in (200, 404):
                info(f"Index '{index_name}' deleted (reset).")

        # Verifica se l'indice esiste già
        r = _get(index_url)
        if r and r.status_code == 200:
            ok(f"Index '{index_name}' already exists, skipping creation.")
            continue

        # Carica il mapping dal file
        try:
            with open(mapping_file, encoding="utf-8") as f:
                mapping = json.load(f)
        except FileNotFoundError:
            warn(f"Mapping file not found: {mapping_file}, creating index without mapping.")
            mapping = {}

        r = _put(index_url, mapping)
        if r and r.status_code in (200, 201):
            ok(f"Index '{index_name}' created with mapping.")
        else:
            body = r.text if r else "no response"
            err(f"Failed to create index '{index_name}': {body}")

# ─── Kafka Connect – registrazione connettori ──────────────────────────────────

def _post_with_retry(url: str, payload: dict, retries: int = 6, delay: int = 8):
    """POST con retry e backoff — utile dopo una delete su Kafka Connect."""
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=30,
                              headers={"Content-Type": "application/json"})
            return r
        except requests.RequestException as exc:
            if attempt < retries:
                info(f"  POST attempt {attempt}/{retries} failed ({exc}), retrying in {delay}s...")
                time.sleep(delay)
            else:
                return None


def _list_connector_names() -> list[str]:
    """Ritorna i nomi di tutti i connettori registrati su Kafka Connect."""
    r = _get(f"{CONNECT_URL}/connectors")
    if r and r.status_code == 200:
        return r.json()
    return []


def _delete_connector(name: str) -> bool:
    r = _delete(f"{CONNECT_URL}/connectors/{name}")
    if r and r.status_code in (204, 200, 404):
        return True
    return False


def cleanup_old_connectors():
    """
    Rimuove il vecchio elasticsearch-sink se presente:
    il consumer Python lo sostituisce e tenerlo causerebbe doppia indicizzazione.
    """
    existing = _list_connector_names()
    sink_candidates = [n for n in existing if "elasticsearch" in n.lower() or "elastic" in n.lower()]
    for name in sink_candidates:
        info(f"Removing old ES sink connector '{name}' (replaced by Python consumer)...")
        if _delete_connector(name):
            ok(f"Old connector '{name}' removed.")
            time.sleep(3)
        else:
            warn(f"Could not remove '{name}', check manually.")


def register_connectors(reset: bool = False):
    step("Registering Kafka Connect connectors")

    connector_files = [
        f for f in os.listdir(CONNECTORS_DIR)
        if f.endswith(".json")
    ]

    if not connector_files:
        warn("No connector JSON files found in ./connectors/")
        return

    existing = _list_connector_names()

    for filename in connector_files:
        filepath = os.path.join(CONNECTORS_DIR, filename)
        with open(filepath, encoding="utf-8") as f:
            connector_cfg = json.load(f)

        name = connector_cfg.get("name")
        if not name:
            warn(f"Connector file '{filename}' has no 'name' field, skipping.")
            continue

        # Cerca match case-insensitive tra i connettori esistenti
        existing_match = next((n for n in existing if n.lower() == name.lower()), None)
        # Cerca anche per prefisso (es. 'tourism-mongodb-source' matcha 'mongodb-source')
        if not existing_match:
            existing_match = next(
                (n for n in existing if name.lower() in n.lower() or n.lower() in name.lower()),
                None
            )

        connector_url = f"{CONNECT_URL}/connectors/{existing_match or name}"

        if reset and existing_match:
            info(f"Deleting connector '{existing_match}' (reset)...")
            if _delete_connector(existing_match):
                ok(f"Connector '{existing_match}' deleted.")
                time.sleep(5)  # attendi che KC processi la delete
                existing_match = None  # dovrà essere ricreato
                connector_url = f"{CONNECT_URL}/connectors/{name}"
            else:
                warn(f"Could not delete '{existing_match}'.")

        if existing_match:
            # Controlla se è già RUNNING: in quel caso non toccare nulla
            r_status = _get(f"{CONNECT_URL}/connectors/{existing_match}/status")
            already_running = (
                r_status and r_status.status_code == 200
                and r_status.json().get("connector", {}).get("state") == "RUNNING"
            )
            if already_running:
                ok(f"Connector '{existing_match}' already RUNNING, skipping update. (Use --reset to force.)")
            else:
                info(f"Connector '{existing_match}' exists but not RUNNING, updating config...")
                r = _put(f"{CONNECT_URL}/connectors/{existing_match}/config", connector_cfg["config"])
                if r and r.status_code in (200, 201):
                    ok(f"Connector '{existing_match}' updated.")
                else:
                    body = r.text if r else "no response"
                    err(f"Failed to update connector '{existing_match}': {body}")
        else:
            info(f"Registering new connector '{name}'...")
            r = _post_with_retry(f"{CONNECT_URL}/connectors", connector_cfg)
            if r and r.status_code in (200, 201):
                ok(f"Connector '{name}' registered.")
            else:
                body = r.text if r else "no response (timeout after retries)"
                err(f"Failed to register connector '{name}': {body}")


def check_connector_status():
    step("Checking connector status")
    r = _get(f"{CONNECT_URL}/connectors?expand=status")
    if not r or r.status_code != 200:
        warn("Could not retrieve connector status.")
        return

    connectors = r.json()
    for name, details in connectors.items():
        state = details.get("status", {}).get("connector", {}).get("state", "UNKNOWN")
        tasks = details.get("status", {}).get("tasks", [])
        task_states = [t.get("state", "?") for t in tasks]
        if state == "RUNNING" and all(s == "RUNNING" for s in task_states):
            ok(f"  {name}: {state} | tasks: {task_states}")
        else:
            warn(f"  {name}: {state} | tasks: {task_states}")

# ─── Summary finale ────────────────────────────────────────────────────────────

def print_summary():
    step("Pipeline Summary")
    print(f"""
  {BOLD}MongoDB{RESET}           → localhost:27017   (replica set rs0)
  {BOLD}Kafka{RESET}             → localhost:9092
  {BOLD}Kafka Connect{RESET}     → localhost:8083     {CYAN}http://localhost:8083/connectors{RESET}
  {BOLD}Elasticsearch{RESET}     → localhost:9200     {CYAN}http://localhost:9200/_cat/indices?v{RESET}

  {BOLD}Indici ES:{RESET}
    • accomodations   {CYAN}http://localhost:9200/accomodations/_count{RESET}
    • attractions     {CYAN}http://localhost:9200/attractions/_count{RESET}

  {BOLD}Consumer log:{RESET}
    docker logs -f tourism-consumer
""")

# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Setup script – avvia e configura l'intera pipeline tourism."
    )
    parser.add_argument("--skip-compose", action="store_true",
                        help="Non eseguire docker compose up (container già avviati).")
    parser.add_argument("--skip-seed", action="store_true",
                        help="Non eseguire i seeder MongoDB.")
    parser.add_argument("--reset", action="store_true",
                        help="Cancella indici ES e connettori prima di ricrearli.")
    args = parser.parse_args()

    print(f"\n{BOLD}{CYAN}{'═' * 55}")
    print("  Tourism Pipeline Setup")
    print(f"{'═' * 55}{RESET}\n")

    # 1. Docker Compose
    if not args.skip_compose:
        compose_up()
    else:
        info("Skipping docker compose up.")

    # 2. Health checks
    step("Waiting for services")
    es_ok      = wait_for_service("Elasticsearch", f"{ES_URL}/_cluster/health")
    mongo_ok   = wait_for_service("MongoDB",       "http://localhost:27017")
    connect_ok = wait_for_kafka_connect()

    if not es_ok or not connect_ok:
        err("One or more critical services failed to start. Aborting.")
        sys.exit(1)

    # 3. Reset MongoDB se richiesto
    if args.reset and not args.skip_seed:
        step("Resetting MongoDB")
        drop_mongo_db()

    # 4. Seeding
    if not args.skip_seed:
        run_seeders()
    else:
        info("Skipping MongoDB seeding.")

    # 5. Elasticsearch indices + mapping
    setup_es_indices(reset=args.reset)

    # 6. Kafka Connect connectors
    #    Prima rimuovi il vecchio ES sink (il consumer Python lo sostituisce)
    cleanup_old_connectors()
    register_connectors(reset=args.reset)

    # Piccola attesa per dare tempo al connettore di avviarsi
    time.sleep(5)
    check_connector_status()

    # 6. Summary
    print_summary()
    ok("Setup complete! The consumer is running inside Docker and will sync data to ES.")


if __name__ == "__main__":
    main()
