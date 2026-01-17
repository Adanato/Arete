"""Stats infrastructure adapters."""

from .connect_stats import ConnectStatsRepository
from .direct_stats import DirectStatsRepository

__all__ = ["ConnectStatsRepository", "DirectStatsRepository"]
