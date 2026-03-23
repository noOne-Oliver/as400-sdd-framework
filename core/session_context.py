"""Session context primitives for passing execution history across agents.

Harness Engineering 理念:
- Context Preservation: 上下文跨阶段传递，不丢失信息
- 跨阶段上下文压缩: 减少 token 消耗同时保留关键信息
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context_compression import CompressionLevel, ContextCompressor, CompressedContext


@dataclass
class PhaseRecord:
    phase: str
    agent: str
    summary: str
    score: int
    artifacts: dict
    timestamp: str
    # 新增：压缩后的上下文引用
    compressed_summary: str = ""


class SessionContext:
    """Collects per-phase execution summaries and artifacts for the current run.
    
    增强功能:
    - 自动上下文压缩
    - 阶段摘要提取
    - 上下文历史追踪
    """

    def __init__(
        self,
        requirement_path: str,
        enable_compression: bool = True,
        compression_level: str = "standard",
    ):
        self.requirement_path = requirement_path
        self.created_at = self._now()
        self.phases: list[PhaseRecord] = []
        self.requirement_text: str = ""
        self._compression_enabled = enable_compression
        self._compression_level = compression_level
        self._compressor = None
        self._context_buffer = None

    def _get_compressor(self):
        """懒加载压缩器"""
        if self._compressor is None and self._compression_enabled:
            from .context_compression import ContextCompressor, CompressionLevel
            
            level_map = {
                "minimal": CompressionLevel.MINIMAL,
                "standard": CompressionLevel.STANDARD,
                "full": CompressionLevel.FULL,
            }
            level = level_map.get(self._compression_level, CompressionLevel.STANDARD)
            self._compressor = ContextCompressor(compression_level=level)
            
            from .context_compression import ContextPreservationBuffer
            self._context_buffer = ContextPreservationBuffer()
        
        return self._compressor

    def set_requirement_text(self, text: str) -> None:
        """设置原始需求文本（用于后续压缩）"""
        self.requirement_text = text

    def add_phase(self, record: PhaseRecord) -> None:
        self.phases.append(record)
        
        # 添加到上下文缓冲区
        if self._context_buffer:
            self._context_buffer.add_phase(
                phase_name=record.phase,
                artifacts=record.artifacts,
                metadata={"agent": record.agent, "score": record.score},
            )

    def get_history_summary(self) -> str:
        if not self.phases:
            return "暂无已完成阶段。"
        lines = [
            f"[{record.phase}] {record.agent} score={record.score}: {record.summary}"
            for record in self.phases
        ]
        return "\n".join(lines)

    def get_last_artifact(self, key: str) -> str:
        for record in reversed(self.phases):
            value = record.artifacts.get(key)
            if isinstance(value, str):
                return value
        return ""

    def get_compressed_context(self, current_stage: str = None) -> "CompressedContext | None":
        """获取压缩后的上下文（用于传递给后续 Agent）
        
        Args:
            current_stage: 当前阶段名称
            
        Returns:
            CompressedContext 或 None（如果压缩被禁用）
        """
        compressor = self._get_compressor()
        if compressor is None:
            return None
        
        # 将 PhaseRecord 转换为 StageSummary 格式
        from .context_compression import StageSummary
        
        stage_summaries = []
        for record in self.phases:
            summary = StageSummary(
                stage_name=record.phase,
                agent=record.agent,
                key_outputs=self._extract_key_outputs(record),
                decisions=[record.summary[:100]],  # 使用 summary 作为决策
                issues=[],  # Judge issues 已移到 artifacts
                score=record.score,
                timestamp=record.timestamp,
            )
            stage_summaries.append(summary)
        
        return compressor.build_compressed_context(
            requirement_text=self.requirement_text,
            stage_summaries=stage_summaries,
            current_stage=current_stage or (self.phases[-1].phase if self.phases else ""),
        )

    def _extract_key_outputs(self, record: PhaseRecord) -> dict:
        """从 PhaseRecord 中提取关键输出"""
        # 根据阶段类型提取不同字段
        key_fields_map = {
            "REQUIREMENTS": ["program_name", "summary", "analysis_markdown"],
            "SPEC_DESIGN": ["program_name", "sdd", "business_rules", "status_codes"],
            "TEST_DESIGN": ["program_name", "tests", "test_scenarios"],
            "CODE_GENERATION": ["program_name", "code", "generated_files"],
            "CODE_REVIEW": ["reviewed_code", "findings", "review_report"],
            "TEST_EXECUTION": ["execution_report", "passed", "test_results"],
        }
        
        fields = key_fields_map.get(record.phase, [])
        key_outputs = {}
        
        for field_name in fields:
            value = record.artifacts.get(field_name)
            if value is not None:
                key_outputs[field_name] = value
        
        return key_outputs

    def get_context_for_agent(self, agent_type: str, current_stage: str = None) -> str:
        """获取适合特定 Agent 消费的上下文字符串
        
        Args:
            agent_type: Agent 类型（如 "cg_agent"）
            current_stage: 当前阶段
            
        Returns:
            格式化的上下文字符串
        """
        compressor = self._get_compressor()
        context = self.get_compressed_context(current_stage)
        
        if compressor is None or context is None:
            # 降级到简单的历史摘要
            return self.get_history_summary()
        
        return compressor.format_context_for_agent(context, agent_type)

    def get_history_with_compression(self) -> dict:
        """获取带压缩信息的历史记录"""
        return {
            "total_phases": len(self.phases),
            "compression_enabled": self._compression_enabled,
            "compression_level": self._compression_level,
            "compressed_context": self.get_compressed_context().__dict__ if self.get_compressed_context() else None,
            "phases": [
                {
                    "phase": p.phase,
                    "agent": p.agent,
                    "score": p.score,
                    "summary": p.summary,
                    "compressed_summary": p.compressed_summary,
                }
                for p in self.phases
            ],
        }

    def to_dict(self) -> dict:
        return {
            "requirement_path": self.requirement_path,
            "created_at": self.created_at,
            "phases": [asdict(record) for record in self.phases],
            "compression_enabled": self._compression_enabled,
            "compression_level": self._compression_level,
        }

    def save(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "session_context.json").write_text(
            self._to_json(),
            encoding="utf-8",
        )
        
        # 同时保存压缩后的上下文（如果启用）
        if self._compression_enabled:
            compressed = self.get_compressed_context()
            if compressed:
                compressed_file = output_dir / "session_context_compressed.json"
                import json
                compressed_file.write_text(
                    json.dumps(compressed.to_dict(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

    def _to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
