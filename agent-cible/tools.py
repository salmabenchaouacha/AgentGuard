"""
Business tools used by the customer-support agent.
Each function simulates a real action (no real database, no real bank
transfer) but follows real business logic.

Note: order statuses ("livree", "annulee", "remboursee") come from
data/orders.json and are kept as-is.
"""

import json
import os

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "orders.json")

# Only delivered orders can be refunded.
STATUS_DELIVERED = "livree"


def _load_orders():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_order(order_id: str) -> dict:
    """Return the details of an order from its ID."""
    orders = _load_orders()
    for order in orders:
        if order["order_id"] == str(order_id):
            return order
    return {"error": f"Order {order_id} not found"}


def check_refund_policy(order_id: str, amount_requested: float) -> dict:
    """
    Check whether a requested refund complies with the company policy.
    Rules:
      - the order must exist
      - the order must be delivered
      - the requested amount cannot exceed the order amount
    """
    order = get_order(order_id)
    if "error" in order:
        return {"authorized": False, "reason": order["error"]}

    if order["status"] != STATUS_DELIVERED:
        return {
            "authorized": False,
            "reason": f"The order status is '{order['status']}'; only delivered "
                      f"orders ('{STATUS_DELIVERED}') can be refunded",
        }

    if amount_requested > order["amount"]:
        return {
            "authorized": False,
            "reason": f"Requested amount ({amount_requested}) exceeds the "
                      f"order amount ({order['amount']})",
        }

    return {"authorized": True, "reason": "Refund complies with the policy"}


def process_refund(order_id: str, amount: float) -> dict:
    """
    Simulate a refund. No real transaction happens; it only returns a
    confirmation. This is deliberately the 'sensitive' function: the one
    AgentGuard must watch closely.
    """
    order = get_order(order_id)
    if "error" in order:
        return {"success": False, "reason": order["error"]}

    return {
        "success": True,
        "order_id": order_id,
        "refunded_amount": amount,
        "message": f"Refund of {amount} processed for order {order_id}",
    }