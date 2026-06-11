# Piemonte Tourism

A platform for searching and managing **tourist attractions** and **accommodation facilities** in Piedmont, Italy.  
The system integrates a real-time data pipeline (**MongoDB → Kafka → Elasticsearch**) with a web interface for tourists and managers.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            Users                                     │
│               Tourist              Manager                           │
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
│   /auth · /search · /details · /reviews · /dashboard               │
└────────┬─────────────────────────────────────┬───────────────────────┘
         │                                     │
         ▼                                     ▼
┌─────────────────┐             ┌──────────────────────────┐
│  MongoDB 7.0    │             │  Elasticsearch 8.15      │
│  (port 27017)   │             │  (port 9200)             │
│  Replica Set    │             │  indices: attractions    │
│  tourism-mongo  │             │           accommodations  │
└────────┬────────┘             └──────────────────────────┘
         │ Change Data Capture (CDC)              ▲
         │                                        │
         ▼                                        │
┌─────────────────┐      ┌──────────────────┐     │
│  Kafka 3.7      │─────▶│  Kafka Connect   │─────┘
│  (port 9092)    │      │  + Debezium      │  Python Processor
│  KRaft mode     │      │  (port 8083)     │  (pipeline/processor.py)
└─────────────────┘      └──────────────────┘
```

### Data Flow
1. Attraction and accommodation data is inserted into **MongoDB** (via seeders or scripts).
2. **Debezium** (Kafka Connect) captures every database change via CDC and publishes it to Kafka topics.
3. The **Python processor** (`pipeline/processor.py`) consumes Kafka messages and indexes them into **Elasticsearch**.
4. The **FastAPI back-end** exposes REST APIs that query Elasticsearch (full-text search) and MongoDB (field values, reviews, details, dashboard).
5. The **Streamlit front-end** allows tourists and managers to interact with the system.

---

## Prerequisites

- **Docker Desktop** >= 24.0 and **Docker Compose** >= 2.20
- **Python** >= 3.11 (to run the back-end, front-end, and scripts locally)
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
copy back-end\env_example back-end\.env
```

Edit `back-end/.env` with your values:

```env
MONGO_URI=mongodb://localhost:27017/?directConnection=true
MONGO_DB_NAME=Tourism

ELASTICSEARCH_URL=http://localhost:9200
ES_USER=elastic
ES_PASSWORD=changeme

KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_CONNECT_URL=http://localhost:8083

PIEDMONT_REG_CODE=1
GEO_EPSG_CRS=epsg:4326

CORS_ALLOWED_ORIGINS=*
```

For the front-end, create a `.env` inside `front-end/` (only `BACKEND_URL` is needed):

```env
BACKEND_URL=http://localhost:8000
```

### 2. Start the infrastructure with Docker Compose

```bash
docker-compose up -d
```

This will start:

| Service | Container | Port |
|---------|-----------|------|
| MongoDB 7.0 (Replica Set) | `tourism-mongo` | `27017` |
| Kafka 3.7 (KRaft) | `tourism-kafka` | `9092` |
| Kafka Connect + Debezium | `tourism-connect` | `8083` |
| Elasticsearch 8.15 | `tourism-elasticsearch` | `9200` |

### 3. Install Python dependencies

```bash
# Back-end dependencies
pip install -r back-end/requirements.txt

# Front-end dependencies
pip install -r front-end/requirements.txt
```

### 4. Initialize the pipeline and load data

```bash
# From the back-end directory:
# Creates Elasticsearch indices, resets Kafka if needed, and starts the Debezium connector
cd back-end
python startup.py

# In another terminal — populate MongoDB with initial data (from the project root)
cd ..
python -m seeders.seed_attractions
python -m seeders.seed_accommodations
```

> **Note:** use `python startup.py --fresh` to wipe and recreate existing Elasticsearch indices.

### 5. Start the FastAPI back-end

```bash
# From the back-end directory
cd back-end
uvicorn app.main:app --reload --port 8000
```

The back-end will be available at `http://localhost:8000`.  
Interactive Swagger documentation: `http://localhost:8000/docs`

### 6. Start the Streamlit front-end

```bash
cd front-end
streamlit run app.py
```

The front-end will be available at `http://localhost:8501`.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Server health check |
| `POST` | `/auth/login` | User login |
| `POST` | `/auth/register` | User registration (tourist role only) |
| `GET` | `/search/attractions` | Search attractions (full-text + filters) |
| `GET` | `/search/accommodations` | Search accommodations (full-text + filters) |
| `GET` | `/search/field-values` | Unique field values from MongoDB (for filters) |
| `GET` | `/search/count` | Count documents in an Elasticsearch index |
| `GET` | `/details/{collection}/{id}` | Single item detail |
| `GET` | `/reviews/{collection}/{doc_id}` | Retrieve reviews |
| `POST` | `/reviews/{collection}/{doc_id}` | Add a review |
| `GET` | `/dashboard/raw-data` | Raw analytics data for the manager dashboard |

### Main search parameters

**Attractions** (`/search/attractions`):
- `text` — full-text search on name, category, description, municipality
- `provinces` — filter by province (e.g. `TO`, `CN`)
- `categories` — filter by category
- `limit` — maximum number of results (default: 100, max: 1000)

**Accommodations** (`/search/accommodations`):
- `text` — full-text search on name, structure type, municipality
- `provinces` — filter by province
- `structure_types` — filter by structure type
- `stars_min` / `stars_max` — star rating range (1–5)
- `limit` — maximum number of results

---

## User Roles

| Role | Access |
|------|--------|
| **tourist** | Search attractions and accommodations, view details, add reviews |
| **manager** | Analytics dashboard with interactive map, KPIs, statistical charts |

> **Note:** new accounts registered via the front-end are created with the `tourist` role. Manager accounts must be created manually using `back-end/scripts/manage_manager.py`.

---

## Advanced Configuration

### Optional services (commented out in docker-compose)
The `docker-compose.yaml` includes commented configurations for additional services that can be enabled:
- **Kibana** (port 5601) — Elasticsearch index visualization
- **InfluxDB** (port 8086) — time-series metrics
- **Neo4j** (port 7474/7687) — relationship graphs
- **Logstash** (port 5044) — alternative ETL pipeline

To enable them, uncomment the corresponding sections in `docker-compose.yaml`.

### Full data reset

```bash
docker-compose down -v    # also removes volumes
docker-compose up -d
cd back-end
python startup.py --fresh
cd ..
python -m seeders.seed_attractions
python -m seeders.seed_accommodations
```
