from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, auth, exercises
from app.seed import seed_if_empty

app = FastAPI(title="Plataforma Adaptativa - TCC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(exercises.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup():
    seed_if_empty()


@app.get("/health")
def health():
    return {"status": "ok"}
