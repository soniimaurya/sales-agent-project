"""
Entry point for the FastAPI application.

Run locally:
    uvicorn main:app --reload --port 8000

Railway runs this automatically via the Procfile.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.db.session import init_db
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create DB tables if they don't exist."""
    init_db()
    yield
    # (nothing to teardown)


app = FastAPI(
    title="Persistent Sales Assistant API",
    description=(
        "A conversational sales agent with cross-session memory, "
        "real tool use (catalog search + memory retrieval), and "
        "self-evaluation on every response."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Allow all origins for demo purposes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
