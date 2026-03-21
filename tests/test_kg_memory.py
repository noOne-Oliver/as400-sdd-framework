"""Tests for core/kg_memory.py and KnowledgeGraph cross-run memory."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from core.kg_memory import KGMemory
from core.knowledge_graph import KnowledgeGraph


def test_kg_memory_save_and_load(tmp_path):
    storage = tmp_path / ".kg_memory.json"
    mem = KGMemory(str(storage))

    mem.save_context("ORDPRC", {
        "matched_documents": ["coding_standards.md"],
        "facts": ["状态码: 02成功 08客户无效 09库存不足"],
        "status_codes": ["02", "08", "09"],
        "program_name": "ORDPRC",
    })

    loaded = KGMemory(str(storage))
    ctx = loaded.load_context("ORDPRC")

    assert ctx is not None
    assert ctx["program_name"] == "ORDPRC"
    assert "02" in ctx["status_codes"]
    assert "状态码" in ctx["facts"][0]


def test_kg_memory_get_learned_facts(tmp_path):
    storage = tmp_path / ".kg_memory.json"
    mem = KGMemory(str(storage))

    mem.save_context("ORDPRC", {
        "facts": ["客户验证用CUSTMF", "库存验证用INVPF"],
    })

    facts = mem.get_learned_facts("ORDPRC")
    assert len(facts) == 2
    assert "客户验证" in facts[0]


def test_kg_memory_unknown_returns_empty_list(tmp_path):
    mem = KGMemory(str(tmp_path / ".kg.json"))
    assert mem.get_learned_facts("NOTEXIST") == []


def test_kg_memory_has_memory(tmp_path):
    mem = KGMemory(str(tmp_path / ".kg.json"))
    assert mem.has_memory("ORDPRC") is False
    mem.save_context("ORDPRC", {"facts": []})
    assert mem.has_memory("ORDPRC") is True


def test_kg_memory_clear_one(tmp_path):
    mem = KGMemory(str(tmp_path / ".kg.json"))
    mem.save_context("ORDPRC", {"facts": []})
    mem.save_context("INVCHK", {"facts": []})
    mem.clear("ORDPRC")
    assert mem.has_memory("ORDPRC") is False
    assert mem.has_memory("INVCHK") is True


def test_kg_memory_clear_all(tmp_path):
    mem = KGMemory(str(tmp_path / ".kg.json"))
    mem.save_context("ORDPRC", {"facts": []})
    mem.clear()
    assert mem.has_memory("ORDPRC") is False


def test_kg_recall_integration(tmp_path):
    kg_dir = tmp_path / "knowledge"
    kg_dir.mkdir()
    (kg_dir / "standards.md").write_text("RPGLE standards: use *N for null", encoding="utf-8")

    kg = KnowledgeGraph(knowledge_dir=str(kg_dir), memory_path=str(tmp_path / ".kg.json"))

    kg.learn_from_run("ORDPRC", {
        "matched_documents": ["standards.md"],
        "facts": ["使用*N表示空值"],
        "status_codes": ["02"],
        "program_name": "ORDPRC",
    })

    ctx = kg.recall("ORDPRC")
    assert ctx is not None
    assert "使用*N" in ctx["facts"][0]


def test_kg_recall_returns_none_for_unknown(tmp_path):
    kg = KnowledgeGraph(knowledge_dir=str(tmp_path / "knowledge"), memory_path=str(tmp_path / ".kg.json"))
    assert kg.recall("UNKNOWN") is None
