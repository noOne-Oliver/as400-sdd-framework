"""Living Spec - 规范随代码变化自动更新

Harness Engineering 理念:
- Spec 是 living artifact，不是静态文档
- 代码变化时，Spec 应该同步更新
- Spec 是唯一真实来源（Single Source of Truth）
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class SpecVersion:
    """Spec 版本记录"""
    version: str
    timestamp: str
    content_hash: str
    program_name: str
    changes: list[str] = field(default_factory=list)


class LivingSpec:
    """管理 Spec 的生命周期，确保与代码同步"""

    def __init__(self, spec_path: Path, program_name: str):
        self.spec_path = Path(spec_path)
        self.program_name = program_name
        self.versions_file = self.spec_path.parent / ".spec_versions.json"
        self.current_content = ""
        self.current_hash = ""

        if self.spec_path.exists():
            self.current_content = self.spec_path.read_text(encoding="utf-8")
            self.current_hash = self._compute_hash(self.current_content)

    def _compute_hash(self, content: str) -> str:
        """计算内容的 MD5 哈希"""
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def has_changed(self, new_content: str) -> bool:
        """检查 Spec 内容是否发生变化"""
        return self._compute_hash(new_content) != self.current_hash

    def update(self, new_content: str, changes: list[str]) -> bool:
        """更新 Spec 内容并记录版本"""
        if not self.has_changed(new_content):
            return False

        # 记录版本
        version = SpecVersion(
            version=self._generate_version(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            content_hash=self._compute_hash(new_content),
            program_name=self.program_name,
            changes=changes,
        )

        self._save_version(version)

        # 更新当前内容
        self.spec_path.write_text(new_content, encoding="utf-8")
        self.current_content = new_content
        self.current_hash = version.content_hash

        return True

    def _generate_version(self) -> str:
        """生成版本号"""
        versions = self.load_versions()
        if not versions:
            return "v1.0"
        last_version = versions[0]["version"]
        parts = last_version.split(".")
        if len(parts) == 2:
            major = int(parts[0][1:])
            minor = int(parts[1])
            return f"v{major}.{minor + 1}"
        return "v1.1"

    def _save_version(self, version: SpecVersion):
        """保存版本记录"""
        versions = self.load_versions()
        versions.insert(0, asdict(version))

        # 只保留最近 10 个版本
        self.versions_file.write_text(
            json.dumps(versions[:10], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def load_versions(self) -> list[dict]:
        """加载所有版本记录"""
        if not self.versions_file.exists():
            return []
        try:
            return json.loads(self.versions_file.read_text(encoding="utf-8"))
        except:
            return []

    def get_change_log(self) -> str:
        """获取变更日志"""
        versions = self.load_versions()
        if not versions:
            return "暂无变更记录"

        lines = ["## Spec 变更日志\n"]
        for v in versions[:5]:
            lines.append(f"### {v['version']} ({v['timestamp']})")
            lines.append(f"- 变更: {', '.join(v['changes']) if v['changes'] else '无'}")
            lines.append(f"- Hash: `{v['content_hash'][:8]}`")
            lines.append("")

        return "\n".join(lines)


def sync_spec_with_code(spec_path: Path, code_path: Path, program_name: str) -> dict:
    """同步 Spec 和代码

    当代码发生变化时，检查 Spec 是否需要更新。
    返回变更报告。
    """
    living_spec = LivingSpec(spec_path, program_name)
    changes = []

    # 检查代码是否存在
    if not code_path.exists():
        return {
            "synced": False,
            "changes": [],
            "message": "代码文件不存在"
        }

    # 读取新代码
    new_code = code_path.read_text(encoding="utf-8")

    # 检查关键变更
    code_lower = new_code.lower()

    # 检查文件声明变化
    old_spec = living_spec.current_content
    if "dcl-f" in code_lower and "dcl-f" in old_spec.lower():
        # 检查是否有新的文件声明
        import re
        old_files = set(re.findall(r'dcl-f\s+(\w+)', old_spec, re.IGNORECASE))
        new_files = set(re.findall(r'dcl-f\s+(\w+)', new_code, re.IGNORECASE))

        added = new_files - old_files
        removed = old_files - new_files

        if added:
            changes.append(f"新增文件声明: {', '.join(added)}")
        if removed:
            changes.append(f"移除文件声明: {', '.join(removed)}")

    # 检查状态处理变化
    for status in ["02", "08", "09"]:
        if f"'{status}'" in new_code and f"状态 {status}" not in old_spec:
            changes.append(f"添加状态 {status} 处理逻辑")

    # 检查错误处理变化
    if "monitor" in code_lower and "monitor" not in old_spec.lower():
        changes.append("添加错误处理 (monitor/on-error)")

    # 检查日志写入变化
    if "write" in code_lower and "ordlogpf" in code_lower:
        if "日志写入" not in old_spec:
            changes.append("添加日志写入逻辑")

    # 如果有变更，更新 Spec
    if changes:
        # 生成更新的 Spec
        updated_spec = _generate_updated_spec(old_spec, changes, program_name)
        living_spec.update(updated_spec, changes)

    return {
        "synced": len(changes) > 0,
        "changes": changes,
        "version": living_spec.current_hash[:8] if living_spec.current_hash else None
    }


def _generate_updated_spec(old_spec: str, changes: list[str], program_name: str) -> str:
    """根据代码变更生成更新后的 Spec"""
    changes_section = old_spec

    # 如果有变更，在变更记录中添加
    if "## 变更记录" in old_spec:
        # 追加到现有变更记录
        from datetime import datetime
        new_entry = f"| 1.0 | {datetime.now().strftime('%Y-%m-%d')} | AI Auto | 更新: {', '.join(changes)} |"
        changes_section = old_spec.replace(
            "## 变更记录",
            f"## 变更记录\n{new_entry}"
        )
    else:
        # 添加新的变更记录节
        from datetime import datetime
        changes_section = old_spec + f"\n\n## 变更记录\n| 版本 | 日期 | 变更人 | 说明 |\n| --- | --- | --- | --- |\n| 1.0 | {datetime.now().strftime('%Y-%m-%d')} | AI Auto | 初始版本 |\n| 1.1 | {datetime.now().strftime('%Y-%m-%d')} | AI Auto | 更新: {', '.join(changes)} |\n"

    return changes_section
