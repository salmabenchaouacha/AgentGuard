"""
Target agent API (customer support).
This service is deliberately "naive": it does no monitoring itself.
That is the job of AgentGuard, deployed as a separate service in front of it.
"""
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from pydantic import BaseModel
from agent import run_agent

app = FastAPI(title="Target Agent - Customer Support")


class QueryRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "agent-cible"}


@app.post("/query")
def query(request: QueryRequest):
    """
    Receive a customer request, run the agent, and return the final answer
    together with the full trace of steps (for external monitoring).
    """
    result = run_agent(request.message)
    return result