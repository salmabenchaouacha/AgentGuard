"""
AgentGuard — le proxy de surveillance.
Reçoit les requêtes destinées à l'agent cible, les transmet, capture la
trace complète, applique les règles + le juge IA, et décide de laisser
passer, d'exiger une validation humaine, ou de bloquer la réponse.

C'est un service totalement indépendant de l'agent cible : il ne connaît
que son URL, rien de son code interne.
"""
from dotenv import load_dotenv
load_dotenv()
import os
import time
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

import db
from rules import evaluate_rules, max_severity
from judge import judge_session

def _normalize_url(url: str) -> str:
    """
    Garantit qu'une URL a bien un schéma (http:// ou https://).
    Nécessaire car Render (fromService) injecte parfois juste 'host:port'
    ou 'host', sans protocole, ce qui fait planter httpx sinon.
    """
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"https://{url}"


AGENT_CIBLE_URL = _normalize_url(os.environ.get("AGENT_CIBLE_URL", "http://localhost:8001"))
ENABLE_JUDGE = os.environ.get("ENABLE_JUDGE", "true").lower() == "true"

# Réveil de l'agent cible : sur l'offre gratuite de Render, un service endormi
# répond 502/503 pendant son démarrage (30 à 60 secondes). On réessaie donc
# quelques fois avant d'abandonner.
RETRY_STATUS_CODES = {502, 503, 504}
MAX_ATTEMPTS = int(os.environ.get("AGENT_MAX_ATTEMPTS", "6"))
RETRY_DELAY_SECONDS = float(os.environ.get("AGENT_RETRY_DELAY", "10"))

app = FastAPI(title="AgentGuard - Proxy de surveillance")


@app.on_event("startup")
def startup():
    db.init_db()


class QueryRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "agentguard-proxy", "agent_cible_url": AGENT_CIBLE_URL}


def _call_agent(message: str) -> dict:
    """
    Appelle l'agent cible, en réessayant tant qu'il n'est pas joignable.

    On ne réessaie QUE dans les cas où la requête n'a pas été traitée par
    l'agent : connexion impossible, ou erreur de passerelle (502/503/504).
    Un timeout de lecture n'est volontairement pas réessayé : l'agent a pu
    recevoir la requête et exécuter un outil, et la rejouer risquerait de
    déclencher l'action une deuxième fois.
    """
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = httpx.post(
                f"{AGENT_CIBLE_URL}/query",
                json={"message": message},
                timeout=60.0,
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            last_error = e
        else:
            if resp.status_code not in RETRY_STATUS_CODES:
                resp.raise_for_status()
                return resp.json()
            last_error = RuntimeError(
                f"L'agent cible a répondu {resp.status_code} "
                f"après {attempt} tentative(s)."
            )

        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_DELAY_SECONDS)

    raise last_error


@app.post("/agent/query")
def query(request: QueryRequest):
    """
    Point d'entrée unique pour le client. Remplace l'appel direct à
    l'agent cible : tout passe par ici.
    """
    session_id = db.create_session(request.message)

    try:
        agent_result = _call_agent(request.message)
    except Exception as e:
        db.update_session_status(session_id, "erreur")
        return {
            "session_id": session_id,
            "status": "erreur",
            "response": "Le service est momentanément indisponible.",
            "detail": str(e),
        }

    trace = agent_result.get("trace", [])
    agent_response = agent_result.get("response", "")

    for step in trace:
        db.log_step(session_id, step)

    rule_alerts = evaluate_rules(trace)
    for alert in rule_alerts:
        db.log_alert(session_id, alert["step_number"], alert["rule"], alert["severity"])
    rules_severity = max_severity(rule_alerts)

    judgment = None
    if ENABLE_JUDGE:
        judgment = judge_session(request.message, trace)
        db.log_judgment(session_id, judgment)

    action, final_status = _decide_action(rules_severity, judgment)
    db.update_session_status(session_id, final_status)

    if action == "bloquer":
        final_response = (
            "Votre demande a été mise en attente pour vérification par un agent "
            "humain avant toute action. Un conseiller reviendra vers vous."
        )
    else:
        final_response = agent_response

    return {
        "session_id": session_id,
        "status": final_status,
        "response": final_response,
        "rule_alerts": rule_alerts,
        "judgment": judgment,
    }


def _decide_action(rules_severity: str, judgment: dict | None):
    """
    Combine l'avis des règles et du juge IA pour décider de l'action.
    La règle la plus stricte des deux systèmes l'emporte toujours.
    """
    action_juge = judgment.get("action_recommandee") if judgment else "continuer"

    if rules_severity == "haute" or action_juge == "bloquer":
        return "bloquer", "bloque"
    if rules_severity == "moyenne" or action_juge == "valider_humain":
        return "valider_humain", "alerte"
    return "continuer", "ok"


@app.get("/sessions")
def list_sessions(limit: int = 50):
    """Utilisé par le dashboard pour lister les sessions récentes."""
    return db.get_sessions(limit=limit)


@app.get("/sessions/{session_id}")
def session_detail(session_id: str):
    """Utilisé par le dashboard pour afficher le détail d'une session."""
    detail = db.get_session_detail(session_id)
    if not detail:
        return {"error": "session introuvable"}
    return detail