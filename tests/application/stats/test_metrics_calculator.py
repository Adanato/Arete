import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from arete.application.stats.metrics_calculator import MetricsCalculator
from arete.application.stats.service import FsrsStatsService
from arete.domain.stats.models import (
    CardStatsAggregate,
    FsrsMemoryState,
    ReviewEntry,
)


@pytest.fixture
def calculator():
    return MetricsCalculator()


@pytest.fixture
def mock_repo():
    return AsyncMock()


def test_metrics_calculator_retrievability(calculator):
    # Setup card with last review 1 day ago and stability 10
    now = int(time.time())
    last_review = now - 86400  # 1 day ago
    
    card = CardStatsAggregate(
        card_id=1,
        note_id=1,
        deck_name="Default",
        lapses=0,
        ease=2500,
        interval=10,
        due=0,
        reps=10,
        fsrs=FsrsMemoryState(stability=10.0, difficulty=0.5),
        last_review=last_review
    )
    
    enriched = calculator.enrich(card)
    
    # R = 0.9^(t/S) = 0.9^(1/10) = 0.9^0.1 approx 0.989
    assert enriched.current_retrievability > 0.98
    assert enriched.current_retrievability < 0.99
    assert enriched.stability == 10.0
    assert enriched.difficulty == 0.5


def test_metrics_calculator_lapse_rate(calculator):
    card = CardStatsAggregate(
        card_id=1, note_id=1, deck_name="D", lapses=5, ease=2500,
        interval=1, due=0, reps=10
    )
    enriched = calculator.enrich(card)
    assert enriched.lapse_rate == 0.5


def test_metrics_calculator_volatility(calculator):
    # Volatility needs 3+ reviews
    reviews = [
        ReviewEntry(1, 1000, 3, 5, 1),
        ReviewEntry(1, 2000, 3, 10, 1),
        ReviewEntry(1, 3000, 3, 100, 1), # Big jump -> High volatility
    ]
    card = CardStatsAggregate(
        card_id=1, note_id=1, deck_name="D", lapses=0, ease=2500,
        interval=100, due=0, reps=3, reviews=reviews
    )
    enriched = calculator.enrich(card)
    assert enriched.volatility is not None
    assert enriched.volatility > 0


@pytest.mark.asyncio
async def test_fsrs_stats_service_orchestration(mock_repo):
    service = FsrsStatsService(stats_repo=mock_repo)
    
    mock_repo.get_card_stats.return_value = [
        CardStatsAggregate(
            card_id=1, note_id=1, deck_name="D", lapses=0, ease=2500,
            interval=1, due=0, reps=1
        )
    ]
    
    enriched_list = await service.get_enriched_stats([1])
    
    assert len(enriched_list) == 1
    assert enriched_list[0].card_id == 1
    mock_repo.get_card_stats.assert_called_once_with([1])


@pytest.mark.asyncio
async def test_fsrs_stats_service_weak_prerequisites(mock_repo):
    service = FsrsStatsService(stats_repo=mock_repo)
    
    # One strong card, one weak card (low stability)
    mock_repo.get_card_stats.return_value = [
        CardStatsAggregate(
            card_id=1, note_id=1, deck_name="D", lapses=0, ease=2500,
            interval=100, due=0, reps=10, 
            fsrs=FsrsMemoryState(stability=50.0, difficulty=0.3),
            last_review=int(time.time()) - 86400
        ),
        CardStatsAggregate(
            card_id=2, note_id=2, deck_name="D", lapses=0, ease=2500,
            interval=1, due=0, reps=1,
            fsrs=FsrsMemoryState(stability=2.0, difficulty=0.8),
            last_review=int(time.time()) - 86400
        )
    ]
    
    weak_cards = await service.get_weak_prerequisites([1, 2], stability_threshold=10.0)
    
    assert len(weak_cards) == 1
    assert weak_cards[0].card_id == 2
