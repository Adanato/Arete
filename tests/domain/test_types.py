from arete.domain.models import AnkiDeck


def test_anki_deck_parents_simple():
    deck = AnkiDeck(name="Math::Algebra")
    assert deck.parents == ["Math"]


def test_anki_deck_parents_deep():
    deck = AnkiDeck(name="A::B::C::D")
    assert deck.parents == ["A", "A::B", "A::B::C"]


def test_anki_deck_parents_root():
    deck = AnkiDeck(name="Math")
    assert deck.parents == []


def test_anki_deck_parents_complex():
    deck = AnkiDeck(name="Space::Oddity::Major::Tom")
    assert "Space" in deck.parents
    assert "Space::Oddity" in deck.parents
