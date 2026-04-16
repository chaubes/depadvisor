"""
Pydantic data models for DepAdvisor.

Pydantic models are like Python dataclasses on steroids:
- They validate data automatically (wrong type? You get a clear error)
- They serialize to/from JSON easily
- They provide great IDE autocomplete
- They document your data structure

Every piece of data flowing through our agent will be one of these models.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# ── Enums ────────────────────────────────────────────────────
# Enums define a fixed set of allowed values.
# If someone tries to use "ruby" as an Ecosystem, Pydantic will reject it.


class Ecosystem(str, Enum):
    """Supported language ecosystems."""

    PYTHON = "python"
    NODE = "node"
    JAVA = "java"


class Severity(str, Enum):
    """Vulnerability severity levels (from CVE/OSV databases)."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    """DepAdvisor's update risk classification."""

    CRITICAL = "critical"  # Update immediately (security vulnerability)
    HIGH = "high"  # Update soon (significant improvements/fixes)
    MEDIUM = "medium"  # Update when convenient
    LOW = "low"  # Optional update
    SKIP = "skip"  # Hold for now (too new, too risky)


# ── Core Models ──────────────────────────────────────────────


class DependencyInfo(BaseModel):
    """
    A single dependency parsed from a dependency file.

    Example: In requirements.txt, the line "flask==3.0.0" becomes:
    DependencyInfo(name="flask", current_version="3.0.0", ecosystem=Ecosystem.PYTHON, ...)
    """

    name: str = Field(description="Package name as it appears in the registry")
    current_version: str | None = Field(default=None, description="Currently pinned version, None if unpinned")
    version_constraint: str | None = Field(default=None, description="Version constraint string (e.g., '>=2.0,<3.0')")
    ecosystem: Ecosystem
    is_dev_dependency: bool = Field(default=False)
    source_file: str = Field(description="Which file this was parsed from")


class UpdateCandidate(BaseModel):
    """
    An available update for a dependency.

    This is produced by comparing the current version against
    what's available in the package registry.
    """

    dependency: DependencyInfo
    latest_version: str
    latest_patch: str | None = Field(
        default=None, description="Latest patch within current minor (e.g., 2.1.0 → 2.1.5)"
    )
    latest_minor: str | None = Field(
        default=None, description="Latest minor within current major (e.g., 2.1.0 → 2.3.0)"
    )
    latest_major: str | None = Field(default=None, description="Latest version overall (e.g., 2.1.0 → 3.0.0)")
    versions_behind: int = Field(default=0, description="Number of releases between current and latest")
    days_since_current_release: int | None = None
    days_since_latest_release: int | None = None
    repository_url: str | None = None


class VulnerabilityInfo(BaseModel):
    """A known vulnerability affecting a dependency."""

    cve_id: str | None = None
    osv_id: str | None = None
    summary: str
    severity: Severity
    affected_versions: str = Field(description="Version range affected")
    fixed_version: str | None = Field(default=None, description="Earliest version that fixes this vulnerability")
    published_date: datetime | None = None
    url: str | None = None


class VulnerabilityReport(BaseModel):
    """Vulnerability scan results for a specific dependency."""

    package_name: str
    ecosystem: Ecosystem
    current_version: str
    vulnerabilities: list[VulnerabilityInfo] = []

    @property
    def has_critical(self) -> bool:
        return any(v.severity == Severity.CRITICAL for v in self.vulnerabilities)

    @property
    def has_high(self) -> bool:
        return any(v.severity == Severity.HIGH for v in self.vulnerabilities)

    @property
    def vulnerability_count(self) -> int:
        return len(self.vulnerabilities)


class ChangelogEntry(BaseModel):
    """A single changelog or release entry."""

    version: str
    date: datetime | None = None
    body: str = Field(description="Release notes text (may be truncated)")
    is_breaking: bool = Field(default=False, description="Whether this contains breaking changes")
    url: str | None = None


class ChangelogSummary(BaseModel):
    """Changelog data for a dependency's recent releases."""

    package_name: str
    entries: list[ChangelogEntry] = []
    source: str = Field(description="Where changelog was fetched from: github_releases, changelog_file, none")
    truncated: bool = False


class RiskAssessment(BaseModel):
    """
    LLM-generated risk assessment for a single dependency update.
    This is the core output of the AI analysis.
    """

    package_name: str
    ecosystem: Ecosystem
    current_version: str
    recommended_version: str
    risk_level: RiskLevel
    risk_score: int = Field(ge=1, le=10, description="1=very safe, 10=very risky")
    reason: str = Field(description="Plain English explanation")
    breaking_changes: list[str] = Field(
        default_factory=list, description="Known breaking changes relevant to this update"
    )
    action: str = Field(description="Specific action recommendation")
    confidence: float = Field(ge=0.0, le=1.0, description="LLM's confidence in this assessment")


class AnalysisReport(BaseModel):
    """
    The complete output of a DepAdvisor analysis run.
    This is the final result that gets formatted and shown to the user.
    """

    project_path: str
    ecosystem: Ecosystem
    analyzed_at: datetime
    total_dependencies: int
    total_with_updates: int
    total_vulnerabilities: int
    critical_updates: list[RiskAssessment] = []
    recommended_updates: list[RiskAssessment] = []
    optional_updates: list[RiskAssessment] = []
    skip_updates: list[RiskAssessment] = []
    summary: str = Field(description="LLM-generated executive summary")
    update_order: list[str] = Field(default_factory=list, description="Recommended order of updates by package name")
    errors: list[str] = Field(default_factory=list)
