from agents.cg_agent import CGAgent


def test_cg_agent_generates_code():
    agent = CGAgent()
    analysis = {"program_name": "ORDPRC"}
    output = agent.execute({"analysis": analysis, "sdd": "", "tests": ""})
    assert "ctl-opt" in output["code"].lower()
