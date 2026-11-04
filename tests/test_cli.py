import pytest

from squeeze.cli import main


def test_help_exits_cleanly():
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
