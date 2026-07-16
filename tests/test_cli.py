import sys

import pytest

import cli
import gui
from update_unit_mods import PatchResult


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    # Never block on the drag-and-drop "Press Enter to exit" pause in tests.
    monkeypatch.setattr(cli, "pause_if_owns_console", lambda: None)


class TestPrintCliResult:
    def test_reports_no_patches_found(self, capsys):
        cli.print_cli_result("somedir", PatchResult(patches_found=0))
        assert "No patch files found." in capsys.readouterr().out

    def test_reports_updated_and_skipped_counts(self, capsys):
        result = PatchResult(patches_found=3, updated=["a"], no_units=["b"])
        cli.print_cli_result("somedir", result)
        out = capsys.readouterr().out
        assert "Checked 3 patch file(s)" in out
        assert "Updated 1 patch file(s)" in out
        assert "Skipped 1 patch file(s)" in out

    def test_reports_corrupted_files_to_stderr(self, capsys):
        result = PatchResult(patches_found=1, corrupted_files=["bad.patch_0"])
        cli.print_cli_result("somedir", result)
        err = capsys.readouterr().err
        assert "Found 1 corrupted patch file(s)" in err
        assert "bad.patch_0" in err


class TestRunCli:
    def test_exits_with_error_when_no_game_path_configured(self, monkeypatch, capsys):
        monkeypatch.setattr(cli, "get_cached_game_data_path", lambda: None)

        with pytest.raises(SystemExit) as exc:
            cli.run_cli(None, ["somedir"])

        assert exc.value.code == 1
        assert "no game data directory configured" in capsys.readouterr().err

    def test_uses_cached_path_when_none_given(self, monkeypatch, tmp_path):
        inited = {}
        monkeypatch.setattr(cli, "get_cached_game_data_path", lambda: str(tmp_path))
        monkeypatch.setattr(cli, "is_valid_game_data_path", lambda p: True)
        monkeypatch.setattr(cli, "init_game_resources", lambda p: inited.setdefault("path", p))
        monkeypatch.setattr(cli, "process_patch_folder", lambda d: PatchResult(directory=d))
        patch_dir = tmp_path / "patches"
        patch_dir.mkdir()

        with pytest.raises(SystemExit) as exc:
            cli.run_cli(None, [str(patch_dir)])

        assert exc.value.code == 0
        assert inited["path"] == str(tmp_path)

    def test_reports_error_for_missing_patch_directory(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(cli, "init_game_resources", lambda p: None)

        with pytest.raises(SystemExit) as exc:
            cli.run_cli(str(tmp_path), [str(tmp_path / "missing")])

        assert exc.value.code == 1
        assert "is not a directory" in capsys.readouterr().err

    def test_exit_code_reflects_corrupted_files(self, monkeypatch, tmp_path):
        monkeypatch.setattr(cli, "init_game_resources", lambda p: None)
        monkeypatch.setattr(
            cli,
            "process_patch_folder",
            lambda d: PatchResult(directory=d, patches_found=1, corrupted_files=["bad.patch_0"]),
        )
        patch_dir = tmp_path / "patches"
        patch_dir.mkdir()

        with pytest.raises(SystemExit) as exc:
            cli.run_cli(str(tmp_path), [str(patch_dir)])

        assert exc.value.code == 1


class TestParseArgs:
    def test_parses_game_and_patches(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog", "-g", "C:\\game", "dir1", "dir2"])
        args = cli.parse_args()
        assert args.game == "C:\\game"
        assert args.patches == ["dir1", "dir2"]

    def test_defaults_when_no_args_given(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog"])
        args = cli.parse_args()
        assert args.game is None
        assert args.patches == []

    def test_game_without_patches_is_an_error(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["prog", "-g", "C:\\game"])

        with pytest.raises(SystemExit) as exc:
            cli.parse_args()

        assert exc.value.code == 2
        assert "PATCH_FOLDER" in capsys.readouterr().err


class TestSetupConsoleIo:
    def test_replaces_none_stdout_and_stderr(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "stderr", None)

        cli.setup_console_io()

        assert sys.stdout is not None
        assert sys.stderr is not None

    def test_leaves_existing_stdio_untouched(self, monkeypatch, capsys):
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        cli.setup_console_io()

        assert sys.stdout is original_stdout
        assert sys.stderr is original_stderr


class TestMain:
    def test_dispatches_to_run_cli_when_patches_given(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "argv", ["prog", str(tmp_path)])
        called = {}
        monkeypatch.setattr(
            cli, "run_cli", lambda game_path, patch_dirs: called.setdefault("run_cli", (game_path, patch_dirs))
        )
        monkeypatch.setattr(gui, "run_gui", lambda: called.setdefault("run_gui", True))

        cli.main()

        assert called["run_cli"] == (None, [str(tmp_path)])
        assert "run_gui" not in called

    def test_dispatches_to_run_gui_when_no_args(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog"])
        called = {}
        monkeypatch.setattr(gui, "run_gui", lambda: called.setdefault("run_gui", True))

        cli.main()

        assert called.get("run_gui") is True

    def test_caches_game_path_before_running_cli(self, monkeypatch, tmp_path):
        (tmp_path / "bundles.nxa").touch()
        monkeypatch.setattr(sys, "argv", ["prog", "-g", str(tmp_path), str(tmp_path)])
        called = {}
        monkeypatch.setattr(cli, "set_cached_game_data_path", lambda p: called.setdefault("cached", p))
        monkeypatch.setattr(cli, "run_cli", lambda g, p: called.setdefault("run_cli", (g, p)))

        cli.main()

        assert called["cached"] == str(tmp_path)
        assert called["run_cli"] == (str(tmp_path), [str(tmp_path)])

    def test_exits_with_error_for_invalid_game_path(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(sys, "argv", ["prog", "-g", str(tmp_path), str(tmp_path)])

        with pytest.raises(SystemExit) as exc:
            cli.main()

        assert exc.value.code == 1
        assert "does not look like a Helldivers II data folder" in capsys.readouterr().err
