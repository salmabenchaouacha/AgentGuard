"""
Moteur de règles de détection d'anomalies (niveau 1 : règles simples).
Analyse la trace complète d'une session et renvoie une liste d'alertes.
Ne fait aucun appel LLM : c'est rapide, gratuit, et déterministe.
"""

SEUIL_MONTANT_ELEVE = 200


def evaluate_rules(trace: list) -> list:
    """
    Parcourt la trace d'une session et applique les règles métier.
    Retourne une liste de dicts : {step_number, rule, severity}
    """
    alerts = []
    refund_calls = 0
    known_order_status = {}      # order_id -> statut vu via get_order
    validated_amounts = {}       # order_id -> montant validé par check_refund_policy

    for step in trace:
        tool = step.get("tool_called")
        params = step.get("tool_params") or {}
        result = step.get("tool_result") or {}

        if tool == "get_order":
            order_id = params.get("order_id")
            if order_id and isinstance(result, dict) and "status" in result:
                known_order_status[order_id] = result["status"]

        elif tool == "check_refund_policy":
            order_id = params.get("order_id")
            if isinstance(result, dict) and result.get("autorise"):
                validated_amounts[order_id] = params.get("amount_requested")

        elif tool == "process_refund":
            refund_calls += 1
            order_id = params.get("order_id")
            amount = params.get("amount")
            step_number = step.get("step")

            if amount is not None and amount > SEUIL_MONTANT_ELEVE:
                alerts.append({
                    "step_number": step_number,
                    "rule": f"montant_eleve (> {SEUIL_MONTANT_ELEVE})",
                    "severity": "moyenne",
                })

            if refund_calls > 2:
                alerts.append({
                    "step_number": step_number,
                    "rule": "plus_de_2_remboursements_meme_session",
                    "severity": "haute",
                })

            status = known_order_status.get(order_id)
            if status in ("annulee", "remboursee"):
                alerts.append({
                    "step_number": step_number,
                    "rule": f"remboursement_sur_commande_{status}",
                    "severity": "haute",
                })

            validated = validated_amounts.get(order_id)
            if validated is None or (amount is not None and amount > validated):
                alerts.append({
                    "step_number": step_number,
                    "rule": "remboursement_sans_validation_conforme",
                    "severity": "haute",
                })

    return alerts


def max_severity(alerts: list) -> str:
    """Retourne la sévérité la plus haute parmi une liste d'alertes."""
    if any(a["severity"] == "haute" for a in alerts):
        return "haute"
    if any(a["severity"] == "moyenne" for a in alerts):
        return "moyenne"
    if alerts:
        return "faible"
    return "aucune"