import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from app.routers import auth, search, details, reviews, dashboard, geo
from app.database import get_mongo
import bcrypt

load_dotenv()


def ensure_admin_exists():
    """Creates the 'admin' manager account only if it does not already exist."""
    db = get_mongo()
    if db["users"].find_one({"username": "admin"}) is None:
        pw_hash = bcrypt.hashpw("admin".encode("utf-8"), bcrypt.gensalt())
        db["users"].insert_one({
            "username": "admin",
            "password_hash": pw_hash,
            "role": "manager",
            "email": "",
            "created_at": datetime.now(timezone.utc),
        })
        print("[STARTUP] Manager account 'admin' created successfully.")
    else:
        print("[STARTUP] Manager account 'admin' already exists, skipping.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_admin_exists()
    yield


app = FastAPI(
    title="Piemonte Sistema Turistico API",
    description="Back-end REST per il sistema turistico del Piemonte coordinato con MongoDB ed Elasticsearch.",
    version="1.0.0",
    lifespan=lifespan,
)

current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")

os.makedirs(os.path.join(static_dir, "images", "accommodations"), exist_ok=True)
os.makedirs(os.path.join(static_dir, "images", "attractions"), exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,   
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
app.include_router(search.router,    prefix="/search",    tags=["Search"])
app.include_router(details.router,   prefix="/details",    tags=["Detail"])
app.include_router(reviews.router,   prefix="/reviews",   tags=["Reviews"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(geo.router,       prefix="/geo",       tags=["Graph Analytics"])


@app.get("/health", tags=["Health"])
def health_check():
    """Endpoint di health-check: verifica se l'istanza dell'API risponde correttamente."""
    return {"status": "ok"}