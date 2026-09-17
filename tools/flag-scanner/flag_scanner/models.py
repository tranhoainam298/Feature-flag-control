"""Domain models and data structures for Flag Scanner."""

from dataclasses import dataclass, field
from enum import Enum


class FlagStatus(str, Enum):
    DEAD = "DEAD"              # ARCHIVED on server, but still in code
    STALE = "STALE"            # High debt score or STALE on server, still in code
    UNDECLARED = "UNDECLARED"  # In code, but not present on server
    ORPHAN = "ORPHAN"          # On server, but not referenced in code
    OK = "OK"                  # Normal active flag in code
    UNKNOWN = "UNKNOWN"        # Server not connected or unclassified


@dataclass(frozen=True)
class Occurrence:
    """A specific occurrence of a flag reference in source code."""
    flag_key: str
    file_path: str
    line_number: int
    code_snippet: str


@dataclass
class ServerFlag:
    """Information about a feature flag retrieved from FlagOps server."""
    key: str
    state: str                 # DRAFT, ACTIVE, ROLLED_OUT, STALE, ARCHIVED
    debt_score: int = 0
    is_temporary: bool = False
    recommendations: list[str] = field(default_factory=list)


@dataclass
class FlagReport:
    """Consolidated report for a single flag across code and server."""
    flag_key: str
    status: FlagStatus
    debt_score: int = 0
    occurrences: list[Occurrence] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class ScanSummary:
    """Summary metrics of the scan."""
    total_code_flags: int = 0
    dead: int = 0
    stale: int = 0
    undeclared: int = 0
    orphan: int = 0
    ok: int = 0
    unknown: int = 0
