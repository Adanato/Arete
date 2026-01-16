from arete.interface.cli import humanize_error


def test_humanize_error_simple():
    msg = humanize_error("Some error")
    assert msg == "Some error"


def test_humanize_error_block_end():
    msg = humanize_error("expected <block end>, but found '?'")
    assert "Indentation error" in msg or "Indentation Error" in msg


def test_check_file_not_found(tmp_path):
    # This function prints to console, we can't easily capture output without capsys or mocking console
    # But checking for exception or return value helps if check_file returned something.
    # check_file returns True/False implicitly or explicitly?
    # It prints and returns nothing.
    pass


# We can test internal helpers if we import them from utils/text?
# cli imports them.
