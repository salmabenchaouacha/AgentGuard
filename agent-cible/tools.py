"""
Outils métier utilisés par l'agent de support client.
Chaque fonction simule une action réelle (pas de vraie base de données
ni de vrai virement bancaire) mais respecte une vraie logique métier.
"""

import json
import os

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "orders.json")


def _load_orders():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_order(order_id: str) -> dict:
    """Retourne les détails d'une commande à partir de son identifiant."""
    orders = _load_orders()
    for order in orders:
        if order["order_id"] == str(order_id):
            return order
    return {"error": f"Commande {order_id} introuvable"}


def check_refund_policy(order_id: str, amount_requested: float) -> dict:
    """
    Vérifie si un remboursement demandé respecte la politique de l'entreprise.
    Règles :
      - la commande doit exister
      - la commande doit être au statut 'livree'
      - le montant demandé ne peut pas dépasser le montant de la commande
    """
    order = get_order(order_id)
    if "error" in order:
        return {"autorise": False, "raison": order["error"]}

    if order["status"] != "livree":
        return {
            "autorise": False,
            "raison": f"La commande est au statut '{order['status']}', "
                      f"seul le statut 'livree' permet un remboursement",
        }

    if amount_requested > order["amount"]:
        return {
            "autorise": False,
            "raison": f"Montant demandé ({amount_requested}) supérieur au "
                      f"montant de la commande ({order['amount']})",
        }

    return {"autorise": True, "raison": "Remboursement conforme à la politique"}


def process_refund(order_id: str, amount: float) -> dict:
    """
    Simule l'exécution d'un remboursement. Ne fait aucune vraie transaction,
    se contente de renvoyer une confirmation. C'est volontairement une
    fonction 'sensible' : c'est celle qu'AgentGuard doit surveiller de près.
    """
    order = get_order(order_id)
    if "error" in order:
        return {"succes": False, "raison": order["error"]}

    return {
        "succes": True,
        "order_id": order_id,
        "montant_rembourse": amount,
        "message": f"Remboursement de {amount} effectué pour la commande {order_id}",
    }