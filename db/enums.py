from enum import Enum


class MarkerCategory(str, Enum):
    CRIME = "Crime"
    ENVIRONMENT = "Environment"
    INFRASTRUCTURE = "Infrastructure"
    SAFETY = "Safety"
    OTHER = "Other"


class MarkerUrgency(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class MarkerStatus(str, Enum):
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"
