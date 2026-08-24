from enum import StrEnum


class CampaignLifecycleStatus(StrEnum):
    PREPARATION = "PREPARATION"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class SessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


class RuntimeStatus(StrEnum):
    IDLE = "IDLE"
    AGENTS_EVALUATING = "AGENTS_EVALUATING"
    VALIDATING_MESSAGE = "VALIDATING_MESSAGE"
    WAITING_FOR_DM = "WAITING_FOR_DM"
    ERROR = "ERROR"
    ENDED = "ENDED"


class CampaignPlayMode(StrEnum):
    NARRATIVE = "NARRATIVE"
    COMBAT = "COMBAT"


class SheetParseStatus(StrEnum):
    PENDING = "PENDING"
    VALID = "VALID"
    FAILED = "FAILED"


class ProfileStatus(StrEnum):
    READY = "READY"
    NEEDS_REBUILD = "NEEDS_REBUILD"
    GENERATING = "GENERATING"
    FAILED = "FAILED"


class UpdatedBy(StrEnum):
    DM = "DM"
    SYSTEM = "SYSTEM"


class SkillName(StrEnum):
    ATHLETICS = "athletics"
    ACROBATICS = "acrobatics"
    SLEIGHT_OF_HAND = "sleight_of_hand"
    STEALTH = "stealth"
    ARCANA = "arcana"
    HISTORY = "history"
    INVESTIGATION = "investigation"
    NATURE = "nature"
    RELIGION = "religion"
    ANIMAL_HANDLING = "animal_handling"
    INSIGHT = "insight"
    MEDICINE = "medicine"
    PERCEPTION = "perception"
    SURVIVAL = "survival"
    DECEPTION = "deception"
    INTIMIDATION = "intimidation"
    PERFORMANCE = "performance"
    PERSUASION = "persuasion"


class RollMode(StrEnum):
    NORMAL = "NORMAL"
    ADVANTAGE = "ADVANTAGE"
    DISADVANTAGE = "DISADVANTAGE"


class SkillCheckStatus(StrEnum):
    VALID = "VALID"
    VOID = "VOID"


class SkillCheckSystemOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNRESOLVED = "UNRESOLVED"


class SkillCheckDmAdjudication(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"


class DmDraftStatus(StrEnum):
    GENERATING = "GENERATING"
    READY = "READY"
    STALE = "STALE"
    SENT = "SENT"
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    DISCARDED = "DISCARDED"
    FAILED = "FAILED"


class DmDraftTriggerType(StrEnum):
    OPENING = "OPENING"
    CHARACTER_REPLY = "CHARACTER_REPLY"
    SKILL_CHECK_RESULT = "SKILL_CHECK_RESULT"
    MANUAL_ASSIST = "MANUAL_ASSIST"


class MessageSenderType(StrEnum):
    DM = "DM"
    CHARACTER = "CHARACTER"
    SYSTEM = "SYSTEM"


class MessageKind(StrEnum):
    IN_GAME = "IN_GAME"
    OOC = "OOC"
    SYSTEM = "SYSTEM"


class MessageAudience(StrEnum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    DM_ONLY = "DM_ONLY"


class AgentRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class AgentRunStopReason(StrEnum):
    PUBLISHED = "PUBLISHED"
    ALL_SILENT = "ALL_SILENT"
    WAITING_FOR_DM = "WAITING_FOR_DM"
    LIMIT_REACHED = "LIMIT_REACHED"
    STALE = "STALE"
    DM_STOP = "DM_STOP"
    DM_PREEMPTED = "DM_PREEMPTED"
    ERROR = "ERROR"


class LlmPurpose(StrEnum):
    CHARACTER = "CHARACTER"


class LlmInvocationStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SummaryAudience(StrEnum):
    DM = "DM"
    CHARACTER = "CHARACTER"


class MemoryOrigin(StrEnum):
    DM = "DM"
    AUTO = "AUTO"
