# Software Requirements & Architectural Specifications
## Multi-Database Tourism System: "Piemonte Turismo"

---

## 1. Executive Summary & System Overview
This document specifies the functional requirements, non-functional constraints, and architectural patterns for the "Piemonte Turismo" platform. The platform delivers a high-performance geospatial and exploratory experience for tourists looking for accommodations and attractions in the Piedmont region. Concurrently, it empowers enterprise managers with an analytical dashboard for regional resource capacity monitoring and telemetry tracking.

---

## 2. Polyglot Persistence Architecture
To guarantee maximum write/read isolation, horizontal scalability, and optimized query execution, the system rejects a monolithic database approach in favor of **Polyglot Persistence**. Each storage technology is selected based on its underlying mathematical model and data access patterns.

### 2.1 MongoDB: Single Source of Truth & Operational Store
* **Data Model:** Document-Oriented (BSON/JSON-like).
* **Architectural Rationale:** Acts as the foundational backbone and the Single Source of Truth (SSoT). The schema-less nature of document collections handles polymorphic entities gracefully. Reviews are embedded directly within their respective documents to optimize common read pathways.


#### Conceputal model:

![noer_schema](./noer_schema.png)




#### Example documents:

Collection Users
```json
{
    "_id": { "$oid": "60c72b2f9b1d8b2bad123456" },
    "username": "mario_rossi",
    "email": "mario.rossi@example.com",
    "password_hash": "$2b$12$R9hZecE78S2Z2C02c3456e...",
    "role": "tourist",
    "created_at": { "$date": "2026-03-15T10:30:00Z" }
}
```

Collection Accommodations
```json
{
    "name": "B&B Il Cervo Innevato",
    "structure_type": "Bed & Breakfast",
    "sector": "SETTORE EXTRALBERGHIERO",
    "stars": 2,
    "location": {
        "municipality": "Tagliolo Monferrato",
        "province": "AL"
    },
    "position": {
        "type": "Point",
        "coordinates": [
            8.671633643949379,
            44.63570199305244
        ]
    },
    "capacity": {
        "rooms": 7,
        "beds": 15
    },
    "contacts": {
        "phone": "0131 4879804",
        "email": "ilcervoinnevato@gmail.com",
        "website": ""
    },
    "reviews": [],
    "_id": {"$oid": "6a37be28dd3a8bb7423fcd24"}
}
```

Collection Attractions
```json
{
    "category": "Siti UNESCO",
    "name": "Palazzina di caccia di Stupinigi",
    "description": "Una delle residenze sabaude più prestigiose del Piemonte. La costruzione dell'ediﬁcio, pensato per la caccia e le feste della famiglia reale, è stata avviata nel 1729 su progetto di Filippo Juvarra, uno degli architetti più rinomati del XVIII secolo.",
    "location": {
        "municipality": "Nichelino",
        "province": "TO"
    },
    "position": {
        "type": "Point",
        "coordinates": [
            7.605221687729391,
            44.995753792005296
        ]
    },
    "image": "palazzinadicacciadistupinigi.jpg",
    "_id": {"$oid": "6a37b6e8155e20c353455ad6"}
}
```



### 2.2 Elasticsearch: Search Engine & Full-Text Analytics
* **Data Model:** Inverted Index oriented by document.
* **Architectural Rationale:** Offloads heavy string matching, multi-attribute filtering (e.g., by category, classification, or province), and complex text exploration away from the primary operational database. It features sub-millisecond search latencies, instant aggregations, and typographical error tolerance (fuzzy search), protecting the system from bottlenecking during high tourist search concurrency.

#### Mappings:
Mapping Accommodations
```json
{
    "mappings": {
        "properties": {
            "name": { "type": "text", "analyzer": "standard" },
            "structure_type": { "type": "keyword" },
            "stars": { "type": "integer" },
            "location": {
                "properties": {
                    "province": { "type": "keyword" },
                    "municipality": { "type": "keyword" },
                    "address": { "type": "text" }
                }
            },
            "coordinates": { "type": "geo_point" },
            "reviews": { "type": "text", "analyzer": "standard" }
        }
    }
}
```

Mapping Attractions
```json
{
    "mappings": {
        "properties": {
            "name": { "type": "text", "analyzer": "standard" },
            "category": { "type": "keyword" },
            "description": { "type": "text", "analyzer": "standard" },
            "location": {
                "properties": {
                    "province": { "type": "keyword" },
                    "municipality": { "type": "keyword" },
                    "address": { "type": "text" }
                }
            },
            "coordinates": { "type": "geo_point" },
            "reviews": { "type": "text", "analyzer": "standard" }
        }
    }
}
```

### 2.3 Neo4j: Property Graph Database for Geospatial Proximity
* **Data Model:** Labelled Property Graph (Nodes, Edges, and Properties).
* **Architectural Rationale:** Specifically integrated to solve complex relational queries and proximity analysis without incurring the computational overhead of heavy relational JOINs or real-time trigonometric distance math. It maps locations as nodes and establishes `NEAR_TO` relationships with a `distance_km` property if they fall within a 3km radius. This enables rapid extraction of nearby points of interest (e.g., finding top attractions near a chosen accommodation).

#### Nodes and Edges structure:
Node Accommodation
```json
{
    "labels": ["Accommodation"],
    "properties": {
        "id": "acc_12345", 
        "name": "Hotel Piemonte",
        "location": "point({latitude: 45.0708, longitude: 7.6840})" 
    }
}
```

Node Attraction
```json
{
    "labels": ["Attraction"],
    "properties": {
        "id": "att_67890",
        "name": "Museo Egizio",
        "location": "point({latitude: 45.0684, longitude: 7.6844})"
    }
}
```


Relation Accomodation, Attraction
```json
{
    "type": "NEAR_TO",
    "directed": true,
    "properties": {
        "distance_km": 0.27 
    }
}
```

### 2.4 InfluxDB (Planned Specifications): Time-Series Storage
* **Data Model:** Time-Series (Timestamp, Measurements, Tags, Fields).
* **Architectural Rationale:** Configured to ingest and analyze high-frequency, sequential telemetry. InfluxDB is assigned two critical scopes:
    1.  **Infrastructure Diagnostics:** Continuous monitoring of system-wide container health (CPU utilization, memory consumption, network saturation across the polyglot cluster nodes).
    2.  **Business Events:** Storing event data over time (e.g., real-time user registration trends, review posting frequency) to populate historical trend graphs on the manager’s dashboard.



#### Measurements structure:

Diagnostic Measurement
```lineprotocol
measurement,tag_set field_set timestamp
container_metrics,container_name=processor_elk,host=docker_cluster cpu_usage_percent=14.5,memory_usage_mb=182.4 1782060000000000000
container_metrics,container_name=processor_neo4j,host=docker_cluster cpu_usage_percent=22.1,memory_usage_mb=210.8 1782060000000000000
container_metrics,container_name=mongodb,host=docker_cluster cpu_usage_percent=5.2,memory_usage_mb=512.0 1782060000000000000
```

Events Measurement
```lineprotocol
business_telemetry,event_type=user_registration,role=tourist count=1i 1782060120000000000
business_telemetry,event_type=review_created,target_collection=accommodations count=1i 1782060155000000000
business_telemetry,event_type=search_executed,index=attractions response_time_ms=12i 1782060180000000000
```

---


### 2.5 Messaging Infrastructure (Kafka Topics & Semantics)
To decouple the primary store from the specialized read models, Apache Kafka acts as the log-centric ingestion backbone. Debezium pipes changes into specific topics following the naming convention `<ServerName>.<DatabaseName>.<CollectionName>`.

* **`Tourism.Tourism.accommodations`**: Captures mutations from the accommodations collection.
* **`Tourism.Tourism.attractions`**: Captures mutations from the attractions collection.

#### Message Lifecycle & Tombstones
Every message delivered contains an explicit operation flag (`"op"`):
* `"op": "c"` / `"r"` (Create / Read-Snapshot): Propagates the full document under the `"after"` block.
* `"op": "u"` (Update): Supplies partial or complete post-mutation states to incremental indexing loops.
* `"op": "d"` (Delete): Emits the removed document context followed immediately by a **Tombstone Message** (a record with an identical primary key but a completely `null` value payload). Secondary consumers intercept these null payloads to trigger structural cleanups, preventing data leakage and orphaning inside Elasticsearch and Neo4j.

## 3. Change Data Capture (CDC) & Event-Driven Pipeline
Data synchronization across the secondary databases (Elasticsearch and Neo4j) is achieved asynchronously via an **Event-Driven Architecture**.