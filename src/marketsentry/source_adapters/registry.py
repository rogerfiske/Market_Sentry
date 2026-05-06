"""Source adapter registry for Market_Sentry.

Maintains a registry of all available source adapters with lookup by name.
Adapters are registered at import time with their default configurations.
"""

from typing import Dict, List, Optional

from marketsentry.source_adapters.base import SourceAdapter


class SourceAdapterRegistry:
    """Registry of available source adapters.

    Provides registration, lookup, and listing of source adapters.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._adapters: Dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        """Register a source adapter.

        Args:
            adapter: The adapter to register.
        """
        self._adapters[adapter.source_name] = adapter

    def get(self, source_name: str) -> Optional[SourceAdapter]:
        """Look up an adapter by source name.

        Args:
            source_name: Name of the source (e.g., "redfin").

        Returns:
            The adapter if found, None otherwise.
        """
        return self._adapters.get(source_name)

    def list_adapters(self) -> List[SourceAdapter]:
        """Return all registered adapters.

        Returns:
            List of registered adapters.
        """
        return list(self._adapters.values())

    def list_names(self) -> List[str]:
        """Return all registered adapter names.

        Returns:
            List of adapter source names.
        """
        return list(self._adapters.keys())

    def has(self, source_name: str) -> bool:
        """Check if an adapter is registered.

        Args:
            source_name: Name of the source.

        Returns:
            True if the adapter is registered.
        """
        return source_name in self._adapters


# ---------------------------------------------------------------------------
# Default registry with all adapters
# ---------------------------------------------------------------------------

_default_registry: Optional[SourceAdapterRegistry] = None


def get_registry() -> SourceAdapterRegistry:
    """Get the default source adapter registry with all adapters registered.

    Creates and populates the registry on first call. Subsequent calls
    return the same instance.

    Returns:
        The populated SourceAdapterRegistry.
    """
    global _default_registry

    if _default_registry is not None:
        return _default_registry

    from marketsentry.source_adapters.compass_adapter import CompassAdapter
    from marketsentry.source_adapters.county_adapter import CountyAdapter
    from marketsentry.source_adapters.homes_adapter import HomesAdapter
    from marketsentry.source_adapters.realtor_adapter import RealtorAdapter
    from marketsentry.source_adapters.redfin_adapter import RedfinAdapter
    from marketsentry.source_adapters.zillow_adapter import ZillowAdapter

    registry = SourceAdapterRegistry()
    registry.register(RedfinAdapter())
    registry.register(ZillowAdapter())
    registry.register(RealtorAdapter())
    registry.register(HomesAdapter())
    registry.register(CompassAdapter())
    registry.register(CountyAdapter())

    _default_registry = registry
    return _default_registry
