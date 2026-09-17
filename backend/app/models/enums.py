import enum


class MemberRole(str, enum.Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"
    VIEWER = "VIEWER"


class FlagType(str, enum.Enum):
    BOOLEAN = "BOOLEAN"
    STRING = "STRING"
    NUMBER = "NUMBER"
    JSON = "JSON"


class ToggleKind(str, enum.Enum):
    RELEASE = "RELEASE"
    EXPERIMENT = "EXPERIMENT"
    OPS = "OPS"
    PERMISSION = "PERMISSION"


class ApiKeyScope(str, enum.Enum):
    SERVER = "SERVER"
    CLIENT = "CLIENT"


class ConfigValueType(str, enum.Enum):
    STRING = "STRING"
    INT = "INT"
    FLOAT = "FLOAT"
    BOOL = "BOOL"
    JSON = "JSON"


class ConfigFormat(str, enum.Enum):
    PROPERTIES = "PROPERTIES"
    JSON = "JSON"
    YAML = "YAML"


class ChangeRequestStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    CANCELLED = "CANCELLED"


class LifecycleState(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ROLLED_OUT = "ROLLED_OUT"
    STALE = "STALE"
    ARCHIVED = "ARCHIVED"
