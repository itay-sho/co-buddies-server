import enum


class ErrorEnum(enum.Enum):
    OK = 0
    UNAUTHENTICATED = 100
    CONVERSATION_CLOSED = enum.auto()
    SCHEMA_ERROR = enum.auto()
    UNIMPLEMENTED = enum.auto()
    CONVERSATION_NOT_INITIALIZED = enum.auto()
    AUTHENTICATION_TIMEOUT = enum.auto()
    AUTH_FAIL_USER_INACTIVE = enum.auto()
    AUTH_FAIL_INVALID_TOKEN = enum.auto()
    INACTIVENESS_TIMEOUT = enum.auto()

    # KEEP LAST
    UNKNOWN_ERROR = enum.auto()