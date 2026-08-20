from enum import StrEnum


class CampaignLifecycleStatus(StrEnum):
    PREPARATION = "PREPARATION"
    ACTIVE = "ACTIVE"
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
