"""
Anki Bridge Factory
Centralizes the logic for selecting the appropriate Anki adapter.
"""

from arete.application.config import AppConfig
from arete.domain.interfaces import AnkiBridge
from arete.domain.stats.ports import StatsRepository
from arete.infrastructure.adapters.anki_connect import AnkiConnectAdapter
from arete.infrastructure.adapters.anki_direct import AnkiDirectAdapter
from arete.infrastructure.adapters.stats.connect_stats import ConnectStatsRepository
from arete.infrastructure.adapters.stats.direct_stats import DirectStatsRepository


async def get_anki_bridge(config: AppConfig) -> AnkiBridge:
    """
    Returns the appropriate AnkiBridge implementation based on config and responsiveness.
    """
    # 1. Manual selection
    if config.backend == "ankiconnect":
        return AnkiConnectAdapter(url=config.anki_connect_url)

    if config.backend == "direct":
        return AnkiDirectAdapter(anki_base=config.anki_base)

    # 2. Auto selection
    ac = AnkiConnectAdapter(url=config.anki_connect_url)
    if await ac.is_responsive():
        import sys

        print("Backend: AnkiConnect", file=sys.stderr)
        return ac

    import sys

    print("Backend: AnkiDirect", file=sys.stderr)
    return AnkiDirectAdapter(anki_base=config.anki_base)


async def get_stats_repository(config: AppConfig) -> StatsRepository:
    """
    Returns the appropriate StatsRepository implementation based on config.
    """
    # 1. Manual selection
    if config.backend == "ankiconnect":
        return ConnectStatsRepository(url=config.anki_connect_url)

    if config.backend == "direct":
        return DirectStatsRepository(anki_base=config.anki_base)

    # 2. Auto selection: prefer Connect if responsive
    ac = AnkiConnectAdapter(url=config.anki_connect_url)
    if await ac.is_responsive():
        return ConnectStatsRepository(url=config.anki_connect_url)

    return DirectStatsRepository(anki_base=config.anki_base)
