"""DepAdvisor HTTP API server built with FastAPI."""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from depadvisor.agent.graph import run_analysis
from depadvisor.models.schemas import AnalysisReport, Ecosystem


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load .env on server startup."""
    load_dotenv(override=True)
    yield


app = FastAPI(
    title="DepAdvisor API",
    description="AI-powered dependency update advisor",
    version="0.1.0",
    lifespan=lifespan,
)


class AnalyzeRequest(BaseModel):
    """Request body for the /analyze endpoint."""

    project_path: str
    ecosystem: str
    llm_provider: str = "ollama/qwen3:8b"


class AnalyzeResponse(BaseModel):
    """Response body for the /analyze endpoint."""

    status: str
    report: AnalysisReport | None = None
    error: str | None = None


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Run a full dependency analysis."""
    try:
        ecosystem = Ecosystem(request.ecosystem.lower())
    except ValueError:
        return AnalyzeResponse(
            status="error",
            error=f"Unknown ecosystem: {request.ecosystem}. Use: python, node, java",
        )

    try:
        report = await run_analysis(
            project_path=request.project_path,
            ecosystem=ecosystem,
            llm_provider=request.llm_provider,
        )
        return AnalyzeResponse(status="success", report=report)
    except Exception as e:
        return AnalyzeResponse(status="error", error=str(e))


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "depadvisor"}
