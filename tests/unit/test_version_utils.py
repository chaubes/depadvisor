"""Tests for version comparison utilities."""

from depadvisor.utils.version import classify_update, find_latest_in_range


class TestClassifyUpdate:
    def test_patch_update(self):
        assert classify_update("2.1.0", "2.1.5") == "patch"

    def test_minor_update(self):
        assert classify_update("2.1.0", "2.3.0") == "minor"

    def test_major_update(self):
        assert classify_update("2.1.0", "3.0.0") == "major"

    def test_no_update(self):
        assert classify_update("2.1.0", "2.1.0") == "none"

    def test_invalid_version(self):
        assert classify_update("not-a-version", "3.0.0") == "unknown"


class TestFindLatestInRange:
    versions = ["1.0.0", "1.0.1", "1.1.0", "1.2.0", "2.0.0", "2.0.1", "2.1.0", "3.0.0rc1"]

    def test_find_latest_patch(self):
        result = find_latest_in_range(self.versions, "1.0.0", "patch")
        assert result == "1.0.1"

    def test_find_latest_minor(self):
        result = find_latest_in_range(self.versions, "1.0.0", "minor")
        assert result == "1.2.0"

    def test_find_latest_major(self):
        result = find_latest_in_range(self.versions, "1.0.0", "major")
        assert result == "2.1.0"  # Excludes pre-release 3.0.0rc1

    def test_no_updates_available(self):
        result = find_latest_in_range(self.versions, "2.1.0", "patch")
        assert result is None
