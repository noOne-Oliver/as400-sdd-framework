from __future__ import annotations

import json

from core.session_context import PhaseRecord, SessionContext


def test_session_context_add_get_and_save(tmp_path):
    context = SessionContext("examples/order_processing/requirement.txt")

    context.add_phase(
        PhaseRecord(
            phase="REQUIREMENTS",
            agent="ra_agent",
            summary="需求分析阶段确认主程序负责读取待处理订单并覆盖 02/08/09 三种业务状态。",
            score=8,
            artifacts={"analysis_markdown": "# 需求分析报告"},
            timestamp="2026-03-21T00:00:00+00:00",
        )
    )
    context.add_phase(
        PhaseRecord(
            phase="SPEC_DESIGN",
            agent="sd_agent",
            summary="设计阶段补充文件交互、错误处理和日志约束，准备进入测试设计。",
            score=9,
            artifacts={"sdd": "# 软件设计说明书"},
            timestamp="2026-03-21T00:05:00+00:00",
        )
    )

    history_summary = context.get_history_summary()
    assert "REQUIREMENTS" in history_summary
    assert "SPEC_DESIGN" in history_summary
    assert "需求分析阶段确认主程序" in history_summary
    assert context.get_last_artifact("analysis_markdown") == "# 需求分析报告"
    assert context.get_last_artifact("sdd") == "# 软件设计说明书"
    assert context.get_last_artifact("missing") == ""

    context.save(tmp_path)

    payload = json.loads((tmp_path / "session_context.json").read_text(encoding="utf-8"))
    assert payload["requirement_path"] == "examples/order_processing/requirement.txt"
    assert len(payload["phases"]) == 2
    assert payload["phases"][0]["agent"] == "ra_agent"

