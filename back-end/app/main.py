import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from app.routers import auth, search, details, reviews, dashboard, geo

load_dotenv()


app = FastAPI(
    title="Piemonte Sistema Turistico API",
    description="Back-end REST per il sistema turistico del Piemonte coordinato con MongoDB ed Elasticsearch.",
    version="1.0.0",
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