from __future__ import annotations

import random
from dataclasses import dataclass

from backend.app.agents.character_agent import CharacterAgentResult


@dataclass(frozen=True, slots=True)
class Candidate:
    character_id: str
    character_name: str
    is_directly_addressed: bool
    last_spoken_sequence: int | None
    result: CharacterAgentResult


class SpeakerCoordinator:
    """Pure, deterministic selection that never modifies an Agent candidate."""

    _URGENCY_ORDER = {"IMMEDIATE": 0, "HIGH": 1, "NORMAL": 2}

    def select(self, candidates: list[Candidate], seed: int) -> Candidate | None:
        ranked = self.rank(candidates, seed)
        return ranked[0] if ranked else None

    def rank(self, candidates: list[Candidate], seed: int) -> list[Candidate]:
        """Full priority order, so a rejected candidate can fall through to the next."""
        responders = [item for item in candidates if item.result.decision.decision == "RESPOND"]
        return sorted(responders, key=lambda item: self._priority(item, seed))

    def _priority(self, candidate: Candidate, seed: int) -> tuple[int, int, int, float]:
        decision = candidate.result.decision
        direct_rank = 0 if candidate.is_directly_addressed else 1
        urgency_rank = self._URGENCY_ORDER[decision.urgency]
        last_spoken_rank = candidate.last_spoken_sequence or -1
        tie_breaker = random.Random(f"{seed}:{candidate.character_id}").random()
        return direct_rank, urgency_rank, last_spoken_rank, tie_breaker
