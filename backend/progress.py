"""Bounded versions of the existing CareerQuest progress JSON contract."""

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ShortId = Annotated[str, Field(min_length=1, max_length=128)]
AnswerIndex = Annotated[int, Field(ge=0, le=30, strict=True)]


class SnapshotModel(BaseModel):
    # Old progress files may contain fields added by a newer UI. Only the
    # documented, bounded fields are used as mentor context.
    model_config = ConfigDict(extra="ignore")


class DecisionSnapshot(SnapshotModel):
    scene: int = Field(ge=0, le=20)
    text: str = Field(max_length=1200)
    outcome: str = Field(default="", max_length=3000)
    quality: Literal[0, 1, 2] | None = None
    source: Literal["choice", "free-text"] = "choice"


class EvidenceSnapshot(SnapshotModel):
    id: ShortId
    careerId: ShortId
    enjoyment: int = Field(ge=1, le=5)
    confidence: int = Field(ge=1, le=5)
    decisions: list[DecisionSnapshot] = Field(default_factory=list, max_length=20)
    at: str = Field(default="", max_length=100)


class JournalSnapshot(SnapshotModel):
    id: ShortId
    at: str = Field(default="", max_length=100)
    prompt: str = Field(default="", max_length=1200)
    text: str = Field(max_length=6000)


class DnaSnapshot(SnapshotModel):
    answers: dict[ShortId, Annotated[str, Field(max_length=32)]] = Field(default_factory=dict)
    tie: Literal["logical", "spatial", "verbal", "inter", "intra", "bodily", "musical", "naturalistic",
                 "existential", "fluid", "learning", "adapt", "creative"] | None = None
    recon: int | None = Field(default=None, ge=0, le=2)

    @field_validator("answers")
    @classmethod
    def bound_answers(cls, value):
        if len(value) > 200:
            raise ValueError("Too many DNA answers")
        return value


class ProgressSnapshot(SnapshotModel):
    v: Literal[1] = 1
    character: int | None = Field(default=None, ge=0, le=3, strict=True)
    answers: list[AnswerIndex] = Field(default_factory=list, max_length=100)
    evidence: list[EvidenceSnapshot] = Field(default_factory=list, max_length=5000)
    tasks: dict[ShortId, list[ShortId]] = Field(default_factory=dict)
    journal: list[JournalSnapshot] = Field(default_factory=list, max_length=5000)
    planCareer: str | None = Field(default=None, max_length=128)
    explored: list[ShortId] = Field(default_factory=list, max_length=100)
    dna: DnaSnapshot = Field(default_factory=DnaSnapshot)

    @field_validator("tasks")
    @classmethod
    def bound_tasks(cls, value):
        if len(value) > 100 or any(len(tasks) > 40 for tasks in value.values()):
            raise ValueError("Too many roadmap tasks")
        return value

    @classmethod
    def validate_payload(cls, value):
        if isinstance(value, cls):
            value = value.model_dump()
        if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > 200_000:
            raise ValueError("Progress data is too large")
        return cls.model_validate(value)
