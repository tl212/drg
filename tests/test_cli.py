"""tests for drg.__main__ — CLI argument parsing and output."""

import json

import pytest

from drg.__main__ import main


class TestCLIOutput:
    def test_basic_output(self, capsys):
        main(["--pdx", "I2109"])
        out = capsys.readouterr().out
        assert "DRG" in out
        assert "282" in out

    def test_json_output(self, capsys):
        main(["--pdx", "I2109", "--json"])
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["drg_code"] == "282"
        assert "mdc" in data
        assert "weight" in data

    def test_secondary_dx_flag(self, capsys):
        main(["--pdx", "I2109", "--sdx", "J9601"])
        out = capsys.readouterr().out
        assert "280" in out

    def test_version_flag(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0

    def test_missing_pdx_exits(self):
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code != 0
