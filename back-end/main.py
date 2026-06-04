"""
Back-end FastAPI — entry point.
Avvio locale (dalla root del progetto):
    python back-end/main.py
    oppure (dalla cartella back-end):
    uvicorn main:app --reload --port 8000

Docs: http://localhost:8000/docs
"""
import sys
import os

# Aggiunge la cartella back-end al path per permettere l'import dei router
# quando il file viene eseguito come script (python back-end/main.py)
sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, search, detail, reviews, dashboard

app = FastAPI(
    title="Piemonte Tourism API",
    description="Back-end REST per il sistema turistico del Piemonte.",
    version="1.0.0",
)

# ── CORS (permette al front-end Streamlit di chiamare l'API) ──────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # in produzione, restringere all'host Streamlit
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Router inclusi ────────────────────────────────────────────────────────────
app.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
app.include_router(search.router,    prefix="/search",    tags=["Search"])
app.include_router(detail.router,    prefix="/detail",    tags=["Detail"])
app.include_router(reviews.router,   prefix="/reviews",   tags=["Reviews"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])


@app.get("/health", tags=["Health"])
def health_check():
    """Endpoint di health-check: restituisce ok se il server è attivo."""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True,
                app_dir=os.path.dirname(__file__))
