from __future__ import annotations

from agents.cr_agent import CRAgent


def test_cr_agent_checklist_passes_for_valid_mock_program():
    agent = CRAgent()
    code = """**FREE
ctl-opt dftactgrp(*no);
dcl-f ORDPF usage(*update:*input) keyed;
dcl-proc Main;
    monitor;
        WriteOrderLog('1': '1': '02': 'ok');
        WriteOrderLog('1': '1': '08': 'invalid');
        WriteOrderLog('1': '1': '09': 'short');
    on-error;
        WriteOrderLog('SYSTEM': 'SYSTEM': '99': 'error');
    endmon;
    *inlr = *on;
end-proc;
"""

    result = agent._run_checklist(code, "ORDPRC")

    assert result.passed is True
    assert result.failed_checks == []
    assert all(result.checks.values())


def test_cr_agent_checklist_fails_when_mandatory_items_missing():
    agent = CRAgent()
    code = """**FREE
ctl-opt dftactgrp(*no);
// TODO: fill later
dcl-proc Main;
    dsply ('hello');
end-proc;
"""

    result = agent._run_checklist(code, "ORDPRC")

    assert result.passed is False
    assert "状态码完整性" in result.failed_checks
    assert "monitor/on-error" in result.failed_checks
    assert "日志写入" in result.failed_checks
    assert "文件操作" in result.failed_checks
    assert "程序入口" in result.failed_checks
    assert "无 TODO" in result.failed_checks

