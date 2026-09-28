"""
API de l'agent cible (support client).
Ce service est volontairement "naïf" : il ne fait aucune surveillance
lui-même. C'est le rôle d'AgentGuard, déployé comme un service séparé,
qui se place devant lui.
"""
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from pydantic import BaseModel
from agent import run_agent

app = FastAPI(title="Agent Cible - Support Client")


class QueryRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "agent-cible"}


@app.post("/query")
def query(request: QueryRequest):
    """
    Reçoit une demande client, fait tourner l'agent, renvoie la réponse
    finale ainsi que la trace complète des étapes (pour supervision externe).
    """
    result = run_agent(request.message)
    return result