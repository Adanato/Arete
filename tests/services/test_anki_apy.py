from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arete.services.anki_apy import AnkiApyAdapter


@pytest.mark.asyncio
async def test_apy_run_timeout():
    adapter = AnkiApyAdapter(apy_bin="apy", anki_base=None)

    with patch("asyncio.create_subprocess_exec") as mock_exec:
        # Mock wait_for to raise timeout
        with patch("asyncio.wait_for", side_effect=TimeoutError()):
            rc, out, err = await adapter._run_apy(Path("dummy.md"))

            assert rc == 124
            assert "timeout" in err
            mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_apy_run_success():
    adapter = AnkiApyAdapter(apy_bin="apy", anki_base=None)

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"nid:123\ncid:456", b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        rc, out, err = await adapter._run_apy(Path("dummy.md"))

        assert rc == 0
        assert out == "nid:123\ncid:456"
        mock_exec.assert_called_once()


@pytest.mark.asyncio
async def test_sync_notes_cid_parsing():
    """
    Verify that AnkiApyAdapter correctly parses NID and CID from apy output.
    """
    from arete.domain.types import AnkiNote, WorkItem

    adapter = AnkiApyAdapter(apy_bin="apy", anki_base=None)

    note = AnkiNote(
        model="Basic",
        deck="Test",
        fields={"Front": "Q", "Back": "A"},
        tags=[],
        start_line=1,
        end_line=1,
        source_file=Path("x.md"),
        source_index=1,
    )
    work_item = WorkItem(note, Path("x.md"), 1)

    with (
        patch.object(
            adapter,
            "_run_apy",
            new_callable=AsyncMock,
            return_value=(0, "created count: 1\n * nid: 999999\n * cid: 888888 \n", ""),
        ),
        patch.object(adapter, "_write_temp", return_value=Path("tmp.md")),
    ):
        results = await adapter.sync_notes([work_item])

    assert len(results) == 1
    res = results[0]

    assert res.ok is True
    assert res.new_nid == "999999"
    assert res.new_cid == "888888"


@pytest.mark.asyncio
async def test_sync_notes_failure_propagation():
    """
    Verify error handling in apy adapter.
    """
    from arete.domain.types import AnkiNote, WorkItem

    adapter = AnkiApyAdapter(apy_bin="apy", anki_base=None)
    note = AnkiNote(
        model="Basic",
        deck="Test",
        fields={},
        tags=[],
        start_line=1,
        end_line=1,
        source_file=Path("x.md"),
        source_index=1,
    )
    work_item = WorkItem(note, Path("x.md"), 1)

    with (
        patch.object(
            adapter, "_run_apy", new_callable=AsyncMock, return_value=(1, "", "some error occurred")
        ),
        patch.object(adapter, "_write_temp", return_value=Path("tmp.md")),
    ):
        results = await adapter.sync_notes([work_item])

    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].error is not None
    assert "some error occurred" in results[0].error


@pytest.mark.asyncio
async def test_sync_notes_integration_content(tmp_path):
    """
    Verify integration between making a note and writing it.
    """
    from arete.domain.types import AnkiNote, WorkItem

    adapter = AnkiApyAdapter(apy_bin="apy", anki_base=None)

    note = AnkiNote(
        model="Basic",
        deck="IntegrationDeck",
        fields={"Front": "Q Content", "Back": "A Content"},
        tags=["tag1"],
        start_line=1,
        end_line=1,
        source_file=Path("x.md"),
        source_index=1,
        nid="111",
    )
    work_item = WorkItem(note, Path("x.md"), 1)

    with patch.object(
        adapter, "_run_apy", new_callable=AsyncMock, return_value=(0, "nid:111\ncid:222", "")
    ):
        with patch.object(adapter, "_write_temp") as mock_write:
            mock_write.return_value = Path("dummy.md")

            await adapter.sync_notes([work_item])

            assert mock_write.called
            content_arg = mock_write.call_args[0][0]

            assert "nid: 111" in content_arg
            assert "deck: IntegrationDeck" in content_arg
            assert "## Front" in content_arg
            assert "Q Content" in content_arg


@pytest.mark.asyncio
async def test_sync_notes_duplicate_error():
    """
    Verify behavior on duplicate error.
    """
    from arete.domain.types import AnkiNote, WorkItem

    adapter = AnkiApyAdapter(apy_bin="apy", anki_base=None)
    note = AnkiNote(
        model="Basic",
        deck="Test",
        fields={},
        tags=[],
        start_line=1,
        end_line=1,
        source_file=Path("x.md"),
        source_index=1,
    )
    work_item = WorkItem(note, Path("x.md"), 1)

    with (
        patch.object(
            adapter,
            "_run_apy",
            new_callable=AsyncMock,
            return_value=(1, "", "Error: duplicate note"),
        ),
        patch.object(adapter, "_write_temp", return_value=Path("tmp.md")),
    ):
        results = await adapter.sync_notes([work_item])

    assert len(results) == 1
    res = results[0]

    assert res.ok is False
    assert res.error is not None
    assert "duplicate note" in res.error
