"""Abstract base class for dependency file parsers."""

from abc import ABC, abstractmethod

from depadvisor.models.schemas import DependencyInfo, Ecosystem


class BaseParser(ABC):
    """
    Base class that all ecosystem parsers must implement.

    Why use an abstract base class?
    - It defines a contract: every parser MUST implement `parse()`
    - It ensures consistency: all parsers return the same data type
    - It makes adding new ecosystems easy: just implement this interface
    """

    ecosystem: Ecosystem

    @abstractmethod
    def parse(self, file_path: str) -> list[DependencyInfo]:
        """
        Parse a dependency file and return a list of dependencies.

        Args:
            file_path: Path to the dependency file

        Returns:
            List of DependencyInfo objects

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file format is invalid
        """
        pass

    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the given file."""
        pass
