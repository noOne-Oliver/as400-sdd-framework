"""Lightweight knowledge graph loader for AS400 standards and business context."""

from __future__ import annotations

from pathlib import Path


class KnowledgeGraph:
    """Indexes markdown knowledge assets and exposes simple keyword search."""

    def __init__(self, knowledge_dir: str | Path = "knowledge"):
        self.knowledge_dir = Path(knowledge_dir)
        self.documents = self._load_documents()

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
