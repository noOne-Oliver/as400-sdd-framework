from core.orchestrator import Orchestrator


def test_orchestrator_runs_mock():
    orchestrator = Orchestrator(provider="mock")
    result = orchestrator.run("examples/order_processing/requirement.txt")
    assert result["status"] in {"completed", "waiting_human", "failed"}
    assert "state" in result
