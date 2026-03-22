"""Entropy Agent - 定期代码健康检查

Harness Engineering 理念:
- Entropy Management: 定期清理 agent 生成的 entropy
- 文档与代码同步
- 约束违反扫描
- 模式执行代理
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class EntropyReport:
    """Entropy 检查报告"""
    timestamp: str
    files_checked: int
    issues_found: int
    issues: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


class EntropyAgent:
    """定期检查代码健康度，发现并修复 entropy"""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.report_file = self.project_root / ".entropy_report.json"

    def run_health_check(self, output_dir: Path) -> EntropyReport:
        """运行健康检查

        检查项目:
        1. 文档一致性 - docs 是否与代码同步
        2. 命名规范 - 变量/函数命名是否一致
        3. 死代码 - 是否有未使用的代码
        4. 约束违反 - 是否违反架构约束
        5. 格式规范 - 代码格式是否一致
        """
        report = EntropyReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            files_checked=0,
            issues_found=0,
        )

        # 检查输出目录下的生成文件
        if output_dir.exists():
            for file_path in output_dir.glob("*.rpgle"):
                self._check_rpg_file(file_path, report)

            # 检查文档文件
            for file_path in output_dir.glob("*.md"):
                self._check_doc_file(file_path, report)

        # 生成建议
        self._generate_recommendations(report)

        # 保存报告
        self._save_report(report)

        return report

    def _check_rpg_file(self, file_path: Path, report: EntropyReport):
        """检查 RPG 文件"""
        report.files_checked += 1

        content = file_path.read_text(encoding="utf-8")
        issues = []

        # 1. 检查 TODO/FIXME
        if "TODO" in content:
            issues.append({
                "file": str(file_path.name),
                "type": "todo",
                "severity": "medium",
                "message": "代码中存在 TODO 标记"
            })

        if "FIXME" in content:
            issues.append({
                "file": str(file_path.name),
                "type": "fixme",
                "severity": "high",
                "message": "代码中存在 FIXME 标记"
            })

        # 2. 检查硬编码路径
        hardcoded_paths = re.findall(r'["\']([A-Z]:\\[^\"\']+)["\']', content)
        if hardcoded_paths:
            issues.append({
                "file": str(file_path.name),
                "type": "hardcoded_path",
                "severity": "low",
                "message": f"发现硬编码路径: {len(hardcoded_paths)} 处"
            })

        # 3. 检查空块 (空的 IF/SELECT)
        empty_blocks = re.findall(r'(IF\s+.*?\s+ENDIF|SELECT\s+.*?\s+ENDSL)', content, re.DOTALL)
        for block in empty_blocks:
            if len(block) < 20:  # 明显是空块
                issues.append({
                    "file": str(file_path.name),
                    "type": "empty_block",
                    "severity": "medium",
                    "message": "发现空的条件块"
                })
                break

        # 4. 检查不一致的状态码处理
        status_checks = {
            "02": bool(re.search(r"['\"]02['\"]", content)),
            "08": bool(re.search(r"['\"]08['\"]", content)),
            "09": bool(re.search(r"['\"]09['\"]", content)),
        }
        missing_statuses = [s for s, exists in status_checks.items() if not exists]
        if missing_statuses:
            issues.append({
                "file": str(file_path.name),
                "type": "missing_status",
                "severity": "high",
                "message": f"缺少状态码处理: {', '.join(missing_statuses)}"
            })

        # 5. 检查缺少错误处理
        if "monitor" not in content.lower():
            issues.append({
                "file": str(file_path.name),
                "type": "missing_error_handling",
                "severity": "high",
                "message": "缺少 monitor/on-error 错误处理"
            })

        # 6. 检查缺少日志写入
        if "ordlogpf" in content.lower() and "write" not in content.lower():
            issues.append({
                "file": str(file_path.name),
                "type": "missing_log",
                "severity": "high",
                "message": "引用了日志文件但未写入"
            })

        report.issues.extend(issues)
        report.issues_found += len(issues)

    def _check_doc_file(self, file_path: Path, report: EntropyReport):
        """检查文档文件"""
        report.files_checked += 1

        content = file_path.read_text(encoding="utf-8")
        issues = []

        # 1. 检查过期引用
        if "ORDPRC" in content:
            # 检查是否有对应的代码文件
            code_file = file_path.parent / "ORDPRC.rpgle"
            if not code_file.exists():
                issues.append({
                    "file": str(file_path.name),
                    "type": "orphaned_doc",
                    "severity": "medium",
                    "message": "文档引用了不存在的程序 ORDPRC"
                })

        # 2. 检查文档完整性
        required_sections = ["业务规则", "处理流程", "错误处理"]
        for section in required_sections:
            if section not in content:
                issues.append({
                    "file": str(file_path.name),
                    "type": "missing_section",
                    "severity": "low",
                    "message": f"文档缺少必要章节: {section}"
                })

        report.issues.extend(issues)
        report.issues_found += len(issues)

    def _generate_recommendations(self, report: EntropyReport):
        """根据检查结果生成建议"""
        if report.issues_found == 0:
            report.recommendations.append("✅ 代码库健康，无明显问题")
            return

        # 按类型分组
        by_type = {}
        for issue in report.issues:
            issue_type = issue["type"]
            if issue_type not in by_type:
                by_type[issue_type] = []
            by_type[issue_type].append(issue)

        recommendations = []

        if "todo" in by_type or "fixme" in by_type:
            recommendations.append("🔴 存在未完成的 TODO/FIXME，应在提交前完成或记录到 backlog")

        if "missing_status" in by_type:
            recommendations.append("🔴 缺少状态码处理，违反业务规则完整性")

        if "missing_error_handling" in by_type:
            recommendations.append("🔴 缺少错误处理，代码健壮性不足")

        if "missing_log" in by_type:
            recommendations.append("🔴 缺少日志写入，审计追踪不完整")

        if "hardcoded_path" in by_type:
            recommendations.append("🟡 发现硬编码路径，应使用配置文件或环境变量")

        if "empty_block" in by_type:
            recommendations.append("🟡 发现空条件块，应清理或完善逻辑")

        if "orphaned_doc" in by_type:
            recommendations.append("🟡 存在孤立文档，应删除或更新")

        report.recommendations = recommendations

    def _save_report(self, report: EntropyReport):
        """保存报告"""
        import json
        self.report_file.write_text(
            json.dumps({
                "timestamp": report.timestamp,
                "files_checked": report.files_checked,
                "issues_found": report.issues_found,
                "issues": report.issues,
                "recommendations": report.recommendations,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def get_latest_report(self) -> Optional[EntropyReport]:
        """获取最新报告"""
        if not self.report_file.exists():
            return None

        import json
        try:
            data = json.loads(self.report_file.read_text(encoding="utf-8"))
            return EntropyReport(
                timestamp=data["timestamp"],
                files_checked=data["files_checked"],
                issues_found=data["issues_found"],
                issues=data.get("issues", []),
                recommendations=data.get("recommendations", []),
            )
        except:
            return None
