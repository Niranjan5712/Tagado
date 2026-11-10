from __future__ import annotations

from app.config import get_settings
from app.services.attention import get_attention_items
from app.services.seed import ensure_demo_workspace
from app.services.stats import compute_client_stats
from sqlalchemy import select

from app.db.models import Client


def test_demo_seed_uses_indian_clients_and_attention(db):
    settings = get_settings()
    workspace = ensure_demo_workspace(db, settings)
    clients = list(db.scalars(select(Client).where(Client.workspace_id == workspace.id)))
    names = {client.name for client in clients}
    assert "Kalpataru Retail Pvt Ltd" in names
    assert "Aarohan Logistics Pvt Ltd" in names
    assert "Prakriti Foods Pvt Ltd" in names
    assert "Acme" not in " ".join(names)
    assert "Zenith" not in " ".join(names)
    assert "Northwind" not in " ".join(names)

    aarohan = next(client for client in clients if "Aarohan" in client.name)
    stats = compute_client_stats(db, aarohan.id)
    assert stats.broken_promises >= 2
    assert stats.avg_days_late > 10

    items = get_attention_items(db, workspace.id)
    types = {item.type for item in items}
    assert "issue_raised" in types
    assert "payment_reported" in types
