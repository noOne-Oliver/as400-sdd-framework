"""Cross-Stage Context Compression for Context Preservation.

Harness Engineering 理念:
- Context Preservation: 上下文跨阶段传递，不丢失信息
- 上下文压缩: 减少 token 消耗同时保留关键信息
- 智能摘要: 提取每阶段的关键信息用于后续阶段
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("as400_sdd_framework")


class CompressionLevel(str, Enum):
    """压缩级别"""
    MINIMAL = "minimal"      # 仅保留核心数据
    STANDARD = "standard"    # 标准压缩
    FULL = "full"           # 完整保留


@dataclass
class StageSummary:
    """阶段摘要"""
    stage_name: str
    agent: str
    key_outputs: dict = field(default_factory=dict)
    decisions: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    score: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CompressedContext:
    """压缩后的上下文"""
    requirement_summary: str
    program_name: str
    file_definitions: dict
    business_rules: list[str]
    status_codes: list[str]
    stage_summaries: list[StageSummary]
    critical_decisions: list[str]
    pending_issues: list[str]
    compression_ratio: float = 1.0

    def to_dict(self) -> dict:
        return {
            "requirement_summary": self.requirement_summary,
            "program_name": self.program_name,
            "file_definitions": self.file_definitions,
            "business_rules": self.business_rules,
            "status_codes": self.status_codes,
            "stage_summaries": [s.to_dict() for s in self.stage_summaries],
            "critical_decisions": self.critical_decisions,
            "pending_issues": self.pending_issues,
            "compression_ratio": self.compression_ratio,
        }


class ContextCompressor:
    """上下文压缩器
    
    功能:
    - 跨阶段上下文压缩
    - 智能摘要提取
    - 关键信息保留
    """

    # 每阶段需要保留的关键字段
    STAGE_KEY_FIELDS = {
        "REQUIREMENTS": ["program_name", "summary", "analysis_markdown", "file_definitions"],
        "SPEC_DESIGN": ["program_name", "sdd", "business_rules", "status_codes"],
        "TEST_DESIGN": ["program_name", "tests", "test_scenarios", "coverage"],
        "CODE_GENERATION": ["program_name", "code", "generated_files"],
        "CODE_REVIEW": ["reviewed_code", "findings", "review_report"],
        "TEST_EXECUTION": ["execution_report", "passed", "test_results"],
    }

    # 压缩级别配置
    COMPRESSION_CONFIGS = {
        CompressionLevel.MINIMAL: {
            "max_context_tokens": 500,
            "keep_stage_count": 2,
            "extract_key_fields_only": True,
        },
        CompressionLevel.STANDARD: {
            "max_context_tokens": 1500,
            "keep_stage_count": 4,
            "extract_key_fields_only": False,
        },
        CompressionLevel.FULL: {
            "max_context_tokens": 4000,
            "keep_stage_count": 6,
            "extract_key_fields_only": False,
        },
    }

    def __init__(
        self,
        compression_level: CompressionLevel = CompressionLevel.STANDARD,
        max_context_tokens: int = None,
    ):
        self.compression_level = compression_level
        config = self.COMPRESSION_CONFIGS[compression_level]
        self.max_context_tokens = max_context_tokens or config["max_context_tokens"]
        self.keep_stage_count = config["keep_stage_count"]
        self.extract_key_fields_only = config["extract_key_fields_only"]

    def compress_stage_output(
        self,
        stage_name: str,
        output: dict,
        key_fields: list[str] = None,
    ) -> StageSummary:
        """压缩单个阶段的输出，提取关键信息
        
        Args:
            stage_name: 阶段名称
            output: 阶段原始输出
            key_fields: 要提取的关键字段
            
        Returns:
            StageSummary 阶段摘要
        """
        fields_to_extract = key_fields or self.STAGE_KEY_FIELDS.get(stage_name, [])
        
        key_outputs = {}
        for field_name in fields_to_extract:
            value = output.get(field_name)
            if value is None:
                continue
            
            # 对大文本进行截断
            if isinstance(value, str) and len(value) > 500:
                value = value[:500] + "... [truncated]"
            
            key_outputs[field_name] = value
        
        # 提取分数
        score = 0
        judge_result = output.get("judge_result", {})
        if isinstance(judge_result, dict):
            score = judge_result.get("score", 0)
        
        # 提取决策
        decisions = self._extract_decisions(stage_name, output)
        
        # 提取问题
        issues = judge_result.get("issues", []) if isinstance(judge_result, dict) else []
        
        summary = StageSummary(
            stage_name=stage_name,
            agent=output.get("agent", "unknown"),
            key_outputs=key_outputs,
            decisions=decisions,
            issues=issues,
            score=score,
        )
        
        logger.info(f"Compressed {stage_name}: score={score}, decisions={len(decisions)}, issues={len(issues)}")
        return summary

    def _extract_decisions(self, stage_name: str, output: dict) -> list[str]:
        """从阶段输出中提取关键决策"""
        decisions = []
        
        if stage_name == "REQUIREMENTS":
            # 从需求分析中提取关键结论
            summary = output.get("summary", "")
            if summary:
                decisions.append(f"需求结论: {summary[:100]}")
            
            program_name = output.get("program_name")
            if program_name:
                decisions.append(f"程序名: {program_name}")
        
        elif stage_name == "SPEC_DESIGN":
            # 从设计文档中提取关键决策
            rules = output.get("business_rules", [])
            for rule in rules[:3]:  # 只取前3条
                decisions.append(f"业务规则: {rule[:80]}")
        
        elif stage_name == "TEST_DESIGN":
            # 提取测试策略
            coverage = output.get("coverage", "unknown")
            decisions.append(f"测试覆盖率: {coverage}")
        
        elif stage_name == "CODE_GENERATION":
            # 提取生成的文件列表
            files = output.get("generated_files", {})
            for fname in list(files.keys())[:3]:
                decisions.append(f"生成文件: {fname}")
        
        elif stage_name == "CODE_REVIEW":
            # 提取关键发现
            findings = output.get("findings", [])
            for finding in findings[:3]:
                decisions.append(f"发现: {finding[:80]}")
        
        return decisions

    def build_compressed_context(
        self,
        requirement_text: str,
        stage_summaries: list[StageSummary],
        current_stage: str,
    ) -> CompressedContext:
        """构建压缩后的上下文
        
        Args:
            requirement_text: 原始需求文本
            stage_summaries: 所有阶段的摘要列表
            current_stage: 当前阶段
            
        Returns:
            CompressedContext 压缩后的上下文
        """
        # 提取需求摘要
        req_summary = self._summarize_requirement(requirement_text)
        
        # 获取项目名称（从最早的阶段）
        program_name = "UNKNOWN"
        for summary in stage_summaries:
            if summary.key_outputs.get("program_name"):
                program_name = summary.key_outputs["program_name"]
                break
        
        # 收集所有文件定义
        file_definitions = {}
        for summary in stage_summaries:
            files = summary.key_outputs.get("file_definitions", {})
            if isinstance(files, dict):
                file_definitions.update(files)
        
        # 收集所有业务规则
        business_rules = []
        for summary in stage_summaries:
            rules = summary.key_outputs.get("business_rules", [])
            if isinstance(rules, list):
                business_rules.extend(rules[:5])  # 每个阶段最多5条
        
        # 收集所有状态码
        status_codes = []
        for summary in stage_summaries:
            statuses = summary.key_outputs.get("status_codes", [])
            if isinstance(statuses, list):
                for s in statuses:
                    if s not in status_codes:
                        status_codes.append(s)
        
        # 只保留最近的 N 个阶段
        recent_summaries = stage_summaries[-self.keep_stage_count:]
        
        # 收集关键决策
        critical_decisions = []
        for summary in stage_summaries:
            critical_decisions.extend(summary.decisions[:2])  # 每个阶段最多2条
        
        # 收集未解决的问题
        pending_issues = []
        for summary in stage_summaries:
            pending_issues.extend(summary.issues)
        
        # 计算压缩率
        original_size = len(json.dumps(stage_summaries, ensure_ascii=False))
        compressed_size = len(json.dumps(recent_summaries, ensure_ascii=False))
        compression_ratio = compressed_size / original_size if original_size > 0 else 1.0
        
        return CompressedContext(
            requirement_summary=req_summary,
            program_name=program_name,
            file_definitions=file_definitions,
            business_rules=business_rules[:10],  # 最多10条
            status_codes=status_codes,
            stage_summaries=recent_summaries,
            critical_decisions=critical_decisions[:10],  # 最多10条
            pending_issues=pending_issues[:5],  # 最多5条
            compression_ratio=round(compression_ratio, 2),
        )

    def _summarize_requirement(self, requirement_text: str, max_length: int = 200) -> str:
        """生成需求摘要"""
        if len(requirement_text) <= max_length:
            return requirement_text
        
        # 简单截断 + 省略号
        return requirement_text[:max_length] + "..."

    def format_context_for_agent(
        self,
        context: CompressedContext,
        agent_type: str,
    ) -> str:
        """将压缩上下文格式化为适合 Agent 消费的字符串
        
        Args:
            context: 压缩后的上下文
            agent_type: Agent 类型 (如 "cg_agent", "td_agent")
            
        Returns:
            格式化的上下文字符串
        """
        lines = [
            "## 压缩上下文 (Compressed Context)",
            "",
            f"**项目**: {context.program_name}",
            f"**需求摘要**: {context.requirement_summary}",
            "",
            "### 文件定义",
        ]
        
        for fname, fdesc in context.file_definitions.items():
            lines.append(f"- {fname}: {fdesc}")
        
        lines.extend([
            "",
            "### 业务规则",
        ])
        for rule in context.business_rules[:5]:
            lines.append(f"- {rule}")
        
        lines.extend([
            "",
            "### 状态码",
            ", ".join(context.status_codes) if context.status_codes else "无",
            "",
            "### 阶段历史",
        ])
        
        for summary in context.stage_summaries:
            lines.append(f"**[{summary.stage_name}]** score={summary.score}")
            for decision in summary.decisions[:2]:
                lines.append(f"  - {decision}")
        
        if context.pending_issues:
            lines.extend([
                "",
                "### ⚠️ 待解决问题",
            ])
            for issue in context.pending_issues:
                lines.append(f"- {issue}")
        
        return "\n".join(lines)


class ContextPreservationBuffer:
    """上下文保留缓冲区
    
    在多阶段执行过程中暂存上下文，
    确保关键信息不会丢失
    """

    def __init__(self, max_phases: int = 10):
        self.max_phases = max_phases
        self.buffer: list[dict] = []
        self.key_values: dict[str, Any] = {}  # 始终保留的关键值

    def add_phase(
        self,
        phase_name: str,
        artifacts: dict,
        metadata: dict = None,
    ) -> None:
        """添加阶段输出到缓冲区"""
        entry = {
            "phase": phase_name,
            "artifacts": artifacts,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        
        self.buffer.append(entry)
        
        # 如果超过最大限制，压缩旧条目
        while len(self.buffer) > self.max_phases:
            self._compress_oldest_phase()
        
        # 更新关键值
        self._update_key_values(artifacts)

    def _update_key_values(self, artifacts: dict) -> None:
        """更新始终保留的关键值"""
        key_fields = ["program_name", "requirement_summary", "status_codes"]
        for field in key_fields:
            if field in artifacts:
                self.key_values[field] = artifacts[field]

    def _compress_oldest_phase(self) -> None:
        """压缩最老的阶段，保留摘要"""
        if not self.buffer:
            return
        
        oldest = self.buffer[0]
        
        # 提取摘要信息
        compressed = {
            "phase": oldest["phase"],
            "compressed": True,
            "summary": self._extract_summary(oldest["artifacts"]),
            "timestamp": oldest["timestamp"],
        }
        
        self.buffer[0] = compressed

    def _extract_summary(self, artifacts: dict) -> str:
        """从 artifacts 中提取摘要"""
        summary_parts = []
        for key, value in artifacts.items():
            if isinstance(value, str) and len(value) > 100:
                summary_parts.append(f"{key}: {value[:100]}...")
            else:
                summary_parts.append(f"{key}: {value}")
        return " | ".join(summary_parts[:3])

    def get_context_for_stage(self, stage_name: str) -> dict:
        """获取特定阶段的上下文"""
        # 查找相关阶段
        relevant_entries = [
            entry for entry in self.buffer
            if entry.get("phase") == stage_name or entry.get("compressed")
        ]
        
        return {
            "buffer": relevant_entries,
            "key_values": self.key_values,
        }

    def get_full_context(self) -> dict:
        """获取完整上下文（带压缩）"""
        return {
            "buffer": self.buffer,
            "key_values": self.key_values,
        }

    def clear(self) -> None:
        """清空缓冲区"""
        self.buffer.clear()
        self.key_values.clear()
