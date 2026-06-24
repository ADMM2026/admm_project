# Turismo Piemonte

A platform for searching and managing tourist attractions and accommodation facilities in Piedmont, Italy.
The system integrates a real-time data pipeline (**MongoDB → Kafka → Elasticsearch + Neo4j**) with a web interface for tourists and managers.

> The application content (descriptions, place names, reviews) is in Italian, sourced from open data provided by [Dati Piemonte](https://www.datipiemonte.it/).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            Users                                    │
│               Tourist              Manager                          │
└────────────┬───────────────────────┬────────────────────────────────┘
             │                       │
             ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│               Front-end — Streamlit  (port 8501)                    │
│   Login · Search attractions/accommodations · Detail · Dashboard    │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP REST
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                Back-end — FastAPI  (port 8000)                      │
│   /auth · /search · /details · /reviews · /dashboard                │
└────────┬──────────────────────────────────────────┬─────────────────┘
         │                                          │
         ▼                                          ▼
┌─────────────────┐              ┌───────────────────────────────────┐
│  MongoDB 7.0    │              │  Elasticsearch 8.15               │
│  (port 27017)   │              │  (port 9200)                      │
│  Replica Set    │              │  indices: attractions             │
│  Single source  │              │           accommodations          │
│  of truth       │              └───────────────────────────────────┘
└────────┬────────┘              ┌───────────────────────────────────┐
         │                       │  Neo4j 5.20                       │
         │                       │  (port 7687)                      │
         │                       │  Geospatial proximity graph       │
         │  Change Data Capture  └───────────────────────────────────┘
         │  (Debezium)                          ▲
         ▼                                      │ 
┌─────────────────┐      ┌──────────────────┐   │ 
│  Kafka 3.7      │─────>│  Kafka Connect   │   │ 
│  (port 9092)    │      │  (port 8083)     │   │ 
│  KRaft mode     │      └──────────────────┘   │ 
└─────────────────┘                             │ 
         │                                      │ 
         │        ┌───────────────────────────┐ │ 
         └───────>│  Python Processors        │─┘ 
                  │  processor_elk.py         |
                  │  processor_neo4j.py       |
                  └───────────────────────────┘
```

### Data Flow

1. Attraction and accommodation data is inserted into **MongoDB** (via seeders or the application itself). MongoDB is the **single source of truth**.
2. **Debezium** (Kafka Connect) captures every change via CDC and publishes it to Kafka topics.
3. Two independent **Python processors** consume Kafka messages in parallel:
   - `processor_elk.py` indexes documents into **Elasticsearch** for full-text search.
   - `processor_neo4j.py` maintains a **Neo4j** proximity graph linking nearby attractions and accommodations.
4. The **FastAPI back-end** exposes REST APIs that query Elasticsearch (full-text search) and MongoDB (details, reviews, dashboard).
5. The **Streamlit front-end** allows tourists and managers to interact with the system.

---

## Prerequisites

- **Docker Desktop** >= 24.0 and **Docker Compose** >= 2.20
- **Python** >= 3.11
- **pip** >= 23.0

---

## Quick Start

### 1. Clone the repository and configure environment variables

```bash
git clone <repository-url>
cd ADMM_PROJECT
```

Create a `.env` file inside `back-end/` using the provided example:

```bash
cp back-end/env_example back-end/.env
```

Edit `back-end/.env` with your values:

```env
MONGO_URI=mongodb://localhost:27017/?directConnection=true
MONGO_DB_NAME=Tourism
ELASTICSEARCH_URL=http://localhost:9200
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CONNECT_URL=http://localhost:8083
PIEDMONT_REG_CODE=1
GEO_EPSG_CRS=epsg:4326
CORS_ALLOWED_ORIGINS=*
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=adminneo4j
NEO4J_MAX_DISTANCE_METERS=3000
```

For the front-end, create a `.env` inside `front-end/`:

```env
BACKEND_URL=http://localhost:8000
```

### 2. Start the infrastructure

```bash
docker compose up -d
```

This starts:

| Service | Container | Port |
|---------|-----------|------|
| MongoDB 7.0 (Replica Set) | `tourism-mongo` | `27017` |
| Kafka 3.7 (KRaft) | `tourism-kafka` | `9092` |
| Kafka Connect + Debezium | `tourism-connect` | `8083` |
| Elasticsearch 8.15 | `tourism-elasticsearch` | `9200` |
| Neo4j 5.20 | `tourism-neo4j` | `7474` / `7687` |

### 3. Install Python dependencies

```bash
pip install -r back-end/requirements.txt
pip install -r front-end/requirements.txt
```

### 4. Seed MongoDB and start the pipeline

> This step is only needed on first run. Open **three terminals**.

**Terminal 1 - back-end directory:** initialize the pipeline and start the processors.

```bash
cd back-end
python -m startup --fresh
```

This creates the Elasticsearch indices, registers the Debezium connector, and starts both `processor_elk` and `processor_neo4j` as background processes. On first run, Debezium will perform an **initial snapshot** of MongoDB and replicate everything to Elasticsearch and Neo4j automatically.
It also ensures that a manager account is present, with username `admin` and password `admin`.

**Terminal 2 - back-end directory:** populate MongoDB with initial data.

```bash
cd back-end
python -m seeders.seed_attractions
python -m seeders.seed_accommodations
```

The seeders read from the provided CSV files and insert data into MongoDB. From there, the pipeline picks up the changes automatically and propagates them to Elasticsearch and Neo4j.

> **Important:** the seeders drop and recreate the MongoDB collections on each run. Only use them during initial setup or when you want to fully reload the source data. After the first run, MongoDB is the source of truth - do not re-run the seeders unless you intend a full reset.

### 5. Start the Application

**Terminal 2 - back-end directory:** 
```bash
python -m uvicorn app.main:app --port 8000
```


**Terminal 3 - front-end directory:**
```bash
cd front-end
python -m streamlit run app.py
```

---

## Subsequent runs

On subsequent runs, the pipeline resumes from where it left off. Just:

```bash
docker compose up -d
cd back-end && python -m startup
cd back-end && python -m uvicorn app.main:app --port 8000
cd front-end && python -m streamlit run app.py
```

---

## Full reset

Use this when you want to wipe everything and start from scratch.

```bash
docker compose down -v        # removes all volumes
docker compose up -d
cd back-end
python -m startup --fresh     # wipes Elasticsearch indices and Neo4j graph, re-registers Debezium
python -m seeders.seed_attractions
python -m seeders.seed_accommodations
```

`--fresh` destroys the Kafka topics and consumer group offsets, the Elasticsearch indices, and the Neo4j graph, then recreates them clean. Since Kafka state is gone, Debezium will perform a new full snapshot of MongoDB.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Server health check |
| `POST` | `/auth/login` | User login |
| `POST` | `/auth/register` | User registration (tourist role only) |
| `GET` | `/search/attractions` | Full-text search on attractions |
| `GET` | `/search/accommodations` | Full-text search on accommodations |
| `GET` | `/search/field-values` | Unique field values from MongoDB (for filters) |
| `GET` | `/search/count` | Count documents in an Elasticsearch index |
| `GET` | `/details/{collection}/{id}` | Single document detail with image URL |
| `GET` | `/reviews/{collection}/{doc_id}` | Retrieve last 3 reviews |
| `POST` | `/reviews/{collection}/{doc_id}` | Add a review |
| `GET` | `/dashboard/raw-data` | Raw analytics data for the manager dashboard |
| `GET` | `/geo/accommodations/{id}/nearby-attractions` | Nearby attractions from Neo4j graph |
| `GET` | `/geo/attractions/{id}/cluster-analysis` | Accommodation hubs around an attraction |

Interactive Swagger docs available at `http://localhost:8000/docs`.

### Main search parameters

**Attractions** (`/search/attractions`):
- `text` - full-text search on name, category, description, municipality
- `provinces` - filter by province (e.g. `TO`, `CN`)
- `categories` - filter by category
- `limit` - max results (default: 100, max: 1000)

**Accommodations** (`/search/accommodations`):
- `text` - full-text search on name, structure type, municipality
- `provinces` - filter by province
- `structure_types` - filter by structure type
- `stars_min` / `stars_max` - star rating range (1–5)
- `limit` - max results

---

## User Roles

| Role | Access |
|------|--------|
| **tourist** | Search attractions and accommodations, view details, add reviews |
| **manager** | Analytics dashboard with interactive map, KPIs, statistical charts |

New accounts registered via the front-end are created with the `tourist` role. Manager accounts must be created manually:

```bash
cd back-end
python -m scripts.manage_manager
```
