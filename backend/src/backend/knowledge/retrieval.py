from dataclasses import dataclass, field


@dataclass
class RetrievalResult:
    chunks: list[str] = field(default_factory=list)
    top_score: float = 0.0


async def retrieve_knowledge(query: str) -> RetrievalResult:
    raise NotImplementedError
