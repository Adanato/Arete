"""Property-based tests for ID generation and assignment."""

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from arete.application.sync.id_service import ensure_card_ids, generate_arete_id

ARETE_ID_RE = re.compile(r"^arete_[0-9A-Z]{26}$")


@given(st.integers(min_value=0, max_value=100))
@settings(max_examples=50)
def test_ids_always_match_format(_n):
    """generate_arete_id() always matches arete_[A-Z0-9]{26}."""
    aid = generate_arete_id()
    assert ARETE_ID_RE.match(aid), f"Bad ID format: {aid}"


def test_ids_unique():
    """100 generated IDs are all distinct."""
    ids = {generate_arete_id() for _ in range(100)}
    assert len(ids) == 100


@given(
    cards=st.lists(
        st.fixed_dictionaries(
            {"Front": st.text(min_size=1, max_size=50), "Back": st.text(min_size=1, max_size=50)}
        ),
        min_size=1,
        max_size=5,
    )
)
@settings(max_examples=50)
def test_ensure_ids_idempotent(cards):
    """ensure_card_ids(ensure_card_ids(meta)) assigns 0 on second call."""
    meta = {"cards": cards}
    first = ensure_card_ids(meta)
    assert first == len(cards)
    second = ensure_card_ids(meta)
    assert second == 0


@given(
    cards=st.lists(
        st.fixed_dictionaries(
            {
                "Front": st.text(min_size=1, max_size=50),
                "Back": st.text(min_size=1, max_size=50),
                "id": st.from_regex(r"arete_[A-Z0-9]{26}", fullmatch=True),
            }
        ),
        min_size=1,
        max_size=5,
    )
)
@settings(max_examples=50)
def test_ensure_ids_preserves_existing(cards):
    """Cards with existing id field are untouched."""
    original_ids = [c["id"] for c in cards]
    meta = {"cards": cards}
    assigned = ensure_card_ids(meta)
    assert assigned == 0
    for card, orig_id in zip(meta["cards"], original_ids):
        assert card["id"] == orig_id


@given(
    n_with=st.integers(min_value=0, max_value=3),
    n_without=st.integers(min_value=0, max_value=3),
)
@settings(max_examples=50)
def test_ensure_ids_count_matches(n_with, n_without):
    """Return value == number of cards that lacked id."""
    cards_with = [{"Front": "Q", "Back": "A", "id": generate_arete_id()} for _ in range(n_with)]
    cards_without = [{"Front": "Q", "Back": "A"} for _ in range(n_without)]
    meta = {"cards": cards_with + cards_without}
    assigned = ensure_card_ids(meta)
    assert assigned == n_without


def test_ensure_ids_handles_non_dict_cards():
    """Non-dict items in cards list are skipped, no crash."""
    meta = {"cards": ["not a dict", 42, None, {"Front": "Q", "Back": "A"}]}
    assigned = ensure_card_ids(meta)
    assert assigned == 1
    assert ARETE_ID_RE.match(meta["cards"][3]["id"])


def test_ensure_ids_empty_meta():
    """Empty/missing cards -> returns 0."""
    assert ensure_card_ids({}) == 0
    assert ensure_card_ids({"cards": []}) == 0
    assert ensure_card_ids({"other": "stuff"}) == 0


def test_ensure_ids_non_list_cards():
    """cards not a list -> returns 0."""
    assert ensure_card_ids({"cards": "not a list"}) == 0
