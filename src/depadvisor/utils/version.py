"""
Version comparison utilities.

The `packaging` library handles the complexity of version parsing
across different ecosystems (PEP 440 for Python, semver for Node/Java).
"""

from packaging.version import InvalidVersion, Version


def parse_version(version_str: str) -> Version | None:
    """
    Parse a version string into a comparable Version object.
    Returns None if the version string is invalid.
    """
    try:
        return Version(version_str)
    except InvalidVersion:
        return None


def classify_update(current: str, latest: str) -> str:
    """
    Classify an update as 'patch', 'minor', or 'major'.

    Examples:
        classify_update("2.1.0", "2.1.5") → "patch"
        classify_update("2.1.0", "2.3.0") → "minor"
        classify_update("2.1.0", "3.0.0") → "major"
    """
    curr = parse_version(current)
    lat = parse_version(latest)

    if curr is None or lat is None:
        return "unknown"

    if lat.major > curr.major:
        return "major"
    elif lat.minor > curr.minor:
        return "minor"
    elif lat.micro > curr.micro:
        return "patch"
    else:
        return "none"


def find_latest_in_range(versions: list[str], current: str, update_type: str = "patch") -> str | None:
    """
    Find the latest version within a range.

    Args:
        versions: List of all available version strings
        current: Current version string
        update_type: "patch" (same minor), "minor" (same major), or "major" (any)

    Returns:
        Latest version string matching the criteria, or None
    """
    curr = parse_version(current)
    if curr is None:
        return None

    candidates: list[Version] = []
    for v_str in versions:
        v = parse_version(v_str)
        if v is None or v.is_prerelease or v.is_devrelease:
            continue
        if v <= curr:
            continue

        if update_type == "patch" and (v.major != curr.major or v.minor != curr.minor):
            continue
        if update_type == "minor" and v.major != curr.major:
            continue

        candidates.append(v)

    if not candidates:
        return None

    return str(max(candidates))


def count_versions_between(versions: list[str], current: str, latest: str) -> int:
    """Count the number of stable releases between current and latest."""
    curr = parse_version(current)
    lat = parse_version(latest)
    if curr is None or lat is None:
        return 0

    count = 0
    for v_str in versions:
        v = parse_version(v_str)
        if v is None or v.is_prerelease or v.is_devrelease:
            continue
        if curr < v <= lat:
            count += 1

    return count
