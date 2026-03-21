"""Lightweight knowledge graph loader for AS400 standards and business context."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.kg_memory import KGMemory


class KnowledgeGraph:
    """Indexes markdown knowledge assets and exposes simple keyword search.

    Composes KGMemory to retain cross-run facts.
    """

    def __init__(
        self,
        knowledge_dir: str | Path = "knowledge",
        memory_path: str | Path = "knowledge/.kg_memory.json",
    ):
        self.knowledge_dir = Path(knowledge_dir)
        self.documents = self._load_documents()
        self.memory = KGMemory(memory_path)

    def _load_documents(self) -> dict[str, str]:
        docs: dict[str, str] = {}
        if not self.knowledge_dir.exists():
            return docs

        for path in sorted(self.knowledge_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".yaml", ".yml"}:
                docs[str(path.relative_to(self.knowledge_dir))] = path.read_text(
                    encoding="utf-8"
                )
        return docs

    def search(self, query: str, limit: int = 5) -> list[dict]:
        query_terms = [term.lower() for term in query.split() if term.strip()]
        scored: list[tuple[int, str, str]] = []

        for name, content in self.documents.items():
            score = sum(content.lower().count(term) for term in query_terms)
            if score:
                scored.append((score, name, content))

        scored.sort(reverse=True)
        return [
            {
                "document": name,
                "score": score,
                "excerpt": content[:300].strip(),
            }
            for score, name, content in scored[:limit]
        ]

    def build_context(self, query: str, limit: int = 3) -> str:
        matches = self.search(query, limit=limit)
        if not matches:
            return "No specific knowledge matches were found."

        sections = []
        for match in matches:
            sections.append(
                f"## {match['document']}\n"
                f"Relevance score: {match['score']}\n"
                f"{match['excerpt']}"
            )
        return "\n\n".join(sections)

    def learn_from_run(self, requirement_name: str, kg_state: dict) -> None:
        """Persist KG results after a pipeline run so future runs can recall them."""
        self.memory.save_context(requirement_name, kg_state)

    def recall(self, requirement_name: str) -> Optional[dict]:
        """Retrieve previously learned KG state, or None."""
        return self.memory.load_context(requirement_name)

    def get_learned_facts(self, requirement_name: str) -> list[str]:
        """Return previously learned fact strings for this requirement."""
        return self.memory.get_learned_facts(requirement_name)
