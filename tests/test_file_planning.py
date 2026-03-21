from __future__ import annotations

from agents.cg_agent import CGAgent


def test_cg_agent_plan_files_returns_sorted_file_specs():
    agent = CGAgent()
    analysis = {"program_name": "ORDPRC"}

    files = agent.plan_files(analysis, "# 软件设计说明书\n需要主程序与批处理入口")

    assert files
    assert files[0].filename == "ORDPRC.rpgle"
    assert files[0].type == "rpgle"
    assert files[0].priority == 1
    assert all(file.description for file in files)
    assert [file.priority for file in files] == sorted(file.priority for file in files)
