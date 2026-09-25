import pytest
from api.services.retrieval_service import retrieval_service
from ingestion.unstructured.graph.context import grounded_retrieval_engine

def test_grounded_retrieval_engine():
    res = grounded_retrieval_engine.retrieve_grounded_context("What is the invoice total?")
    assert res["status"] == "success"
    assert "question" in res
    assert "citations" in res

def test_retrieval_service_nl2cypher():
    res = retrieval_service.nl2cypher("Find all invoices with total greater than 500")
    assert res["status"] == "success"
    assert "generated_cypher" in res
    assert "MATCH" in res["generated_cypher"]
