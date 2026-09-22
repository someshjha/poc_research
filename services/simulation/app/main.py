from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .physics import run_simulation

app = FastAPI(title="Research Assistant — Simulation Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SimulationRequest(BaseModel):
    lam: float = Field(0.02, alias="lambda", description="Perturbation strength, in units of mω³/ħ")
    basis_size: int = Field(40, ge=8, le=400)

    class Config:
        populate_by_name = True


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/v1/simulate")
async def simulate(request: SimulationRequest):
    return run_simulation(lam=request.lam, n_basis=request.basis_size)
