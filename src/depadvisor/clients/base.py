"""Abstract base class for package registry clients."""

from abc import ABC, abstractmethod

from depadvisor.models.schemas import DependencyInfo, UpdateCandidate


class BaseRegistryClient(ABC):
    """Base class for package registry API clients."""

    @abstractmethod
    async def get_update_candidates(self, dependency: DependencyInfo) -> UpdateCandidate | None:
        """
        Check if updates are available for a dependency.

        Returns None if the package is not found or has no updates.
        """
        pass
