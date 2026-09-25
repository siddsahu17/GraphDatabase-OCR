import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_list_templates():
    response = client.get("/api/semi-structured/templates")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    domains = [t["domain"] for t in data]
    assert "invoice" in domains

def test_list_documents():
    response = client.get("/api/semi-structured/documents")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_export_csv():
    response = client.get("/api/semi-structured/export/csv")
    assert response.status_code == 200
    assert "document_id" in response.text

def test_export_json():
    response = client.get("/api/semi-structured/export/json")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_grounded_retrieval_endpoint():
    response = client.post("/api/retrieval/grounded", json={"question": "Where is the patient record?"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "answer" in data

def test_nl2cypher_endpoint():
    response = client.post("/api/retrieval/nl2cypher", json={"query": "Get medical bill for patient John Doe"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "generated_cypher" in data
