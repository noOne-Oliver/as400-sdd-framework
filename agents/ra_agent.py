"""Requirements analysis agent."""

from __future__ import annotations

import re

from .base_agent import BaseAgent, ValidationResult


class RAAgent(BaseAgent):
    def __init__(self, llm_client=None):
        super().__init__("ra_agent", llm_client, "prompts/ra_agent")

    def execute(self, input_data: dict) -> dict:
        requirement_text = input_data.get("requirement_text", "").strip()
        program_name = self._extract_program_name(requirement_text)
        steps = self._extract_numbered_lines(requirement_text)
        feedback = input_data.get("feedback", "")
        context_summary = input_data.get("context_summary", "").strip()

        open_questions = []
        if "日志" in requirement_text and "格式" not in requirement_text:
            open_questions.append("ORDLOGPF 的字段结构需要在落地时与现有 DDS 定义核对。")
        if feedback:
            open_questions.append(f"重试反馈: {feedback}")

        analysis_md = self._build_analysis_markdown(
            program_name=program_name,
            requirement_text=requirement_text,
            steps=steps,
            open_questions=open_questions,
            context_summary=context_summary,
        )

        return {
            "program_name": program_name,
            "summary": f"{program_name} 负责读取待处理订单并完成客户、库存、状态、日志闭环。",
            "process_steps": steps,
            "data_entities": ["ORDPF", "CUSTMF", "INVPF", "ORDLOGPF"],
            "business_rules": [
                "状态 01 表示待处理订单。",
                "状态 02 表示订单已确认。",
                "状态 08 表示客户无效。",
                "状态 09 表示库存不足。",
            ],
            "open_questions": open_questions,
            "analysis_markdown": analysis_md,
        }

    def validate_output(self, output: dict) -> ValidationResult:
        issues = []
        if not output.get("summary"):
            issues.append("Requirement summary is missing.")
        if not output.get("process_steps"):
            issues.append("Requirement process steps are missing.")
        if not output.get("analysis_markdown"):
            issues.append("Requirement analysis markdown is missing.")
        return ValidationResult(not issues, issues)

    @staticmethod
    def _extract_program_name(requirement_text: str) -> str:
        match = re.search(r"程序名[:：]\s*([A-Z0-9_]+)", requirement_text)
        return match.group(1) if match else "AS400PGM"

    @staticmethod
    def _extract_numbered_lines(requirement_text: str) -> list[str]:
        steps = []
        for line in requirement_text.splitlines():
            stripped = line.strip()
            if re.match(r"^\d+\.", stripped):
                steps.append(stripped)
        return steps

    @staticmethod
    def _build_analysis_markdown(
        program_name: str,
        requirement_text: str,
        steps: list[str],
        open_questions: list[str],
        context_summary: str,
    ) -> str:
        joined_steps = "\n".join(f"- {step}" for step in steps) or "- 未解析到编号步骤"
        joined_questions = (
            "\n".join(f"- {question}" for question in open_questions)
            if open_questions
            else "- 当前 mock 分析未发现阻塞性问题"
        )
        context_section = context_summary or "暂无上游阶段上下文。"
        return f"""# 需求分析报告

## 执行上下文
{context_section}

## 程序
- 程序名: {program_name}
- 目标: 自动处理待处理订单并记录处理结果

## 原始需求摘录
{requirement_text}

## 处理步骤
{joined_steps}

## 关键文件
- ORDPF: 订单主文件
- CUSTMF: 客户主文件
- INVPF: 库存文件
- ORDLOGPF: 处理日志文件

## 业务规则
- 仅处理状态 = 01 的订单
- 客户不存在或无效时状态更新为 08
- 库存不足时状态更新为 09
- 所有通过验证的订单状态更新为 02
- 每笔订单处理结果必须写入日志

## 风险与待澄清
{joined_questions}
"""
