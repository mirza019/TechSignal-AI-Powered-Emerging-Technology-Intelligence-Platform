from sqlalchemy import select
from app.models import Technology, Evidence


def test_login_and_read_endpoints(client, tokens):
    assert client.get("/api/technologies").status_code == 401
    result = client.post("/api/auth/login", json={"email": "viewer@techsignal.local", "password": "RadarDemo2026!"})
    assert result.status_code == 200 and result.json()["access_token"]
    for path in [
        "/dashboard",
        "/technologies",
        "/radar",
        "/signals",
        "/papers",
        "/startups",
        "/institutions",
        "/pipeline/runs",
        "/settings",
        "/quality",
        "/reports",
    ]:
        response = client.get("/api" + path, headers=tokens["Viewer"])
        assert response.status_code == 200, (path, response.text)


def test_public_demo_role_login(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "public_demo", True)
    monkeypatch.setattr(get_settings(), "seed_demo", True)
    for role in ["Viewer", "Analyst", "Admin"]:
        result = client.post("/api/auth/demo", json={"role": role})
        assert result.status_code == 200
        assert result.json()["user"]["role"] == role
    assert client.post("/api/auth/demo", json={"role": "Owner"}).status_code == 422


def test_rbac_and_writes(client, tokens):
    body = {"name": "Test power converter", "domain": "HVDC", "description": "A test technology", "keywords": ["test power conversion"]}
    assert client.post("/api/technologies", json=body, headers=tokens["Viewer"]).status_code == 403
    response = client.post("/api/technologies", json=body, headers=tokens["Analyst"])
    assert response.status_code == 201
    id = response.json()["id"]
    assert client.put("/api/technologies/" + id, json={**body, "archived": True}, headers=tokens["Analyst"]).status_code == 200
    assert client.post("/api/pipeline/run", json={"provider": "demo"}, headers=tokens["Analyst"]).status_code == 403
    assert client.put("/api/settings/weights", json={}, headers=tokens["Analyst"]).status_code == 403


def test_assessment_rejects_foreign_evidence(client, tokens, db):
    tech = db.scalar(select(Technology))
    foreign = db.scalar(select(Evidence).where(Evidence.technology_id != tech.id))
    body = {
        "horizon": "H2",
        "maturity": 60,
        "confidence": 0.6,
        "notes": "Reviewed primary evidence carefully",
        "evidence_ids": [foreign.id],
    }
    assert client.post(f"/api/technologies/{tech.id}/review", json=body, headers=tokens["Analyst"]).status_code == 422
    body["evidence_ids"] = [db.scalar(select(Evidence.id).where(Evidence.technology_id == tech.id))]
    response = client.post(f"/api/technologies/{tech.id}/review", json=body, headers=tokens["Analyst"])
    assert response.status_code == 200
    assert response.json()["approved"] is True
    assert response.json()["horizon"] == "H2"


def test_report_export_and_query(client, tokens, db):
    tech = db.scalar(select(Technology))
    query = client.post("/api/ai/query", headers=tokens["Viewer"], json={"query": "grid converters", "technology_id": tech.id})
    assert query.status_code == 200 and query.json()["sources"]
    report = client.post(
        "/api/reports/generate", headers=tokens["Analyst"], json={"kind": "Technology Opportunity Report", "technology_id": tech.id}
    )
    assert report.status_code == 201, report.text
    id = report.json()["id"]
    pdf = client.get(f"/api/reports/{id}/export?format=pdf", headers=tokens["Viewer"])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    markdown = client.get(f"/api/reports/{id}/export?format=md", headers=tokens["Viewer"])
    assert "Evidence Sources" in markdown.text
    assert "Configurable H1–H4 technology horizon model" in markdown.text


def test_invalid_weights_and_duplicate_technology(client, tokens):
    assert client.put("/api/settings/weights", headers=tokens["Admin"], json={"research": 3}).status_code == 422
    body = {"name": "Grid-forming converters", "domain": "Grid Stabilization"}
    assert client.post("/api/technologies", headers=tokens["Admin"], json=body).status_code == 409


def test_dataset_switch_preserves_records_and_requires_admin(client, tokens):
    response = client.put("/api/settings/data-mode", json={"is_demo": False}, headers=tokens["Viewer"])
    assert response.status_code == 403
    response = client.put("/api/settings/data-mode", json={"is_demo": False}, headers=tokens["Admin"])
    assert response.status_code == 200
    assert client.get("/api/papers", headers=tokens["Viewer"]).json() == []
    client.put("/api/settings/data-mode", json={"is_demo": True}, headers=tokens["Admin"])
    assert len(client.get("/api/papers", headers=tokens["Viewer"]).json()) == 50
