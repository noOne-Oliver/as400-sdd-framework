from agents.ra_agent import RAAgent


def test_ra_agent_extracts_program_name():
    agent = RAAgent()
    output = agent.execute({"requirement_text": "程序名：ORDPRC\n功能：订单处理"})
    assert output["program_name"] == "ORDPRC"
    assert output["analysis_markdown"]
