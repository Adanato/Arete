from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from o2a.domain.types import AnkiNote, WorkItem
from o2a.services.anki_apy import AnkiApyAdapter


@pytest.fixture
def adapter():
    return AnkiApyAdapter("apy", Path("/tmp/anki_collection"), dry_run=True)


@pytest.mark.asyncio
async def test_anki_apy_misc_methods(adapter):
    assert await adapter.get_model_names() == []
    assert await adapter.get_deck_names() == []
    assert await adapter.ensure_deck("D") is True

    with pytest.raises(ValueError):
        await adapter.get_notes_in_deck("D")
    with pytest.raises(ValueError):
        await adapter.delete_notes([1])
    with pytest.raises(ValueError):
        await adapter.delete_decks(["D"])


@pytest.mark.asyncio
async def test_anki_apy_sync_notes_success(adapter, tmp_path):
    note = AnkiNote(
        model="Basic",
        deck="Default",
        fields={"Front": "f", "Back": "b"},
        tags=[],
        start_line=1,
        end_line=2,
        source_file=Path("test.md"),
        source_index=1,
    )
    item = WorkItem(note=note, source_file=Path("test.md"), source_index=1)

    out = b"* nid: 123\n* cid: 456\n"
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (out, b"")
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        res = await adapter.sync_notes([item])
        assert res[0].ok is True


@pytest.mark.asyncio
async def test_anki_apy_run_apy_failure_logging(adapter, tmp_path):
    note = AnkiNote(
        model="Basic",
        deck="Default",
        fields={"Front": "f"},
        tags=[],
        start_line=1,
        end_line=2,
        source_file=Path("test.md"),
        source_index=1,
    )
    item = WorkItem(note=note, source_file=Path("test.md"), source_index=1)

    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"", b"fail")
    mock_proc.returncode = 1

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        res = await adapter.sync_notes([item])
        assert res[0].ok is False


@pytest.mark.asyncio
async def test_anki_apy_run_apy_timeout(adapter, tmp_path):
    note = AnkiNote(
        model="Basic",
        deck="Default",
        fields={"Front": "f"},
        tags=[],
        start_line=1,
        end_line=2,
        source_file=Path("test.md"),
        source_index=1,
    )
    item = WorkItem(note=note, source_file=Path("test.md"), source_index=1)

    mock_proc = AsyncMock()
    # Mock communicate to raise timeout
    mock_proc.communicate.side_effect = TimeoutError()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch("asyncio.wait_for", side_effect=TimeoutError()):
            res = await adapter.sync_notes([item])
            assert res[0].ok is False
            assert "timeout" in res[0].error


@pytest.mark.asyncio
async def test_anki_apy_run_apy_exception(adapter, tmp_path):
    note = AnkiNote(
        model="Basic",
        deck="Default",
        fields={"Front": "f"},
        tags=[],
        start_line=1,
        end_line=2,
        source_file=Path("test.md"),
        source_index=1,
    )
    item = WorkItem(note=note, source_file=Path("test.md"), source_index=1)

    with patch("asyncio.create_subprocess_exec", side_effect=Exception("Fatal")):
        res = await adapter.sync_notes([item])
        assert res[0].ok is False
        assert "Fatal" in res[0].error


@pytest.mark.asyncio
async def test_anki_apy_unlink_error(adapter, tmp_path):
    note = AnkiNote(
        model="Basic",
        deck="Default",
        fields={"Front": "f"},
        tags=[],
        start_line=1,
        end_line=2,
        source_file=Path("test.md"),
        source_index=1,
    )
    item = WorkItem(note=note, source_file=Path("test.md"), source_index=1)

    f = tmp_path / "to_delete.md"
    f.touch()

    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"* nid: 1\n", b"")
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with patch.object(adapter, "_write_temp", return_value=f):
            with patch("pathlib.Path.unlink", side_effect=OSError("Unlink fail")):
                res = await adapter.sync_notes([item])
                assert res[0].ok is True
