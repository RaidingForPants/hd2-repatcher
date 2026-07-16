import os
import sys

import pytest

import update_unit_mods as uum


class TestIsValidGameDataPath:
    def test_false_when_directory_missing(self, tmp_path):
        assert uum.is_valid_game_data_path(str(tmp_path / "missing")) is False

    def test_false_when_neither_marker_present(self, tmp_path):
        assert uum.is_valid_game_data_path(str(tmp_path)) is False

    def test_true_when_legacy_marker_present(self, tmp_path):
        (tmp_path / "9ba626afa44a3aa3").touch()
        assert uum.is_valid_game_data_path(str(tmp_path)) is True

    def test_true_when_slim_marker_present(self, tmp_path):
        (tmp_path / "bundles.nxa").touch()
        assert uum.is_valid_game_data_path(str(tmp_path)) is True


class TestFindPatchFiles:
    def test_finds_patch_files_recursively(self, tmp_path):
        (tmp_path / "a.patch_0").touch()
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.patch_1").touch()
        (tmp_path / "c.txt").touch()

        found = uum.find_patch_files(str(tmp_path))

        assert sorted(os.path.basename(f) for f in found) == ["a.patch_0", "b.patch_1"]

    def test_empty_list_when_no_patch_files(self, tmp_path):
        (tmp_path / "c.txt").touch()
        assert uum.find_patch_files(str(tmp_path)) == []


class TestProcessPatchFiles:
    def test_aggregates_results_by_status_code(self, monkeypatch):
        def fake_update(path):
            return {
                "u.patch": (uum.UPDATE_SUCCESS, "u.patch"),
                "n.patch": (uum.NO_UNIT_FILES, "n.patch"),
                "c.patch": (uum.CORRUPTED_FILE, "c.patch"),
            }[path]

        monkeypatch.setattr(uum, "update_patch_file", fake_update)

        result = uum.process_patch_files(["u.patch", "n.patch", "c.patch"])

        assert result["updated"] == ["u.patch"]
        assert result["no_units"] == ["n.patch"]
        assert result["corrupted_files"] == ["c.patch"]

    def test_empty_patch_list_returns_empty_result(self):
        assert uum.process_patch_files([]) == {
            "updated": [],
            "no_units": [],
            "corrupted_files": [],
        }


class TestProcessPatchFolder:
    def test_includes_directory_and_patch_count(self, tmp_path, monkeypatch):
        (tmp_path / "a.patch_0").touch()
        monkeypatch.setattr(uum, "update_patch_file", lambda p: (uum.UPDATE_SUCCESS, p))

        result = uum.process_patch_folder(str(tmp_path))

        assert result["directory"] == str(tmp_path)
        assert result["patches_found"] == 1
        assert len(result["updated"]) == 1


class TestPrintCliResult:
    def test_reports_no_patches_found(self, capsys):
        uum.print_cli_result("somedir", {"patches_found": 0})
        out = capsys.readouterr().out
        assert "No patch files found." in out

    def test_reports_updated_and_skipped_counts(self, capsys):
        result = {
            "patches_found": 3,
            "updated": ["a"],
            "no_units": ["b"],
            "corrupted_files": [],
        }
        uum.print_cli_result("somedir", result)
        out = capsys.readouterr().out
        assert "Checked 3 patch file(s)" in out
        assert "Updated 1 patch file(s)" in out
        assert "Skipped 1 patch file(s)" in out

    def test_reports_corrupted_files_to_stderr(self, capsys):
        result = {
            "patches_found": 1,
            "updated": [],
            "no_units": [],
            "corrupted_files": ["bad.patch_0"],
        }
        uum.print_cli_result("somedir", result)
        err = capsys.readouterr().err
        assert "Found 1 corrupted patch file(s)" in err
        assert "bad.patch_0" in err


class TestRunCli:
    def test_exits_with_error_when_no_game_path_configured(self, monkeypatch, capsys):
        monkeypatch.setattr(uum, "get_cached_game_data_path", lambda: None)

        with pytest.raises(SystemExit) as exc:
            uum.run_cli(None, ["somedir"])

        assert exc.value.code == 1
        assert "no game data directory configured" in capsys.readouterr().err

    def test_uses_cached_path_when_none_given(self, monkeypatch, tmp_path):
        monkeypatch.setattr(uum, "get_cached_game_data_path", lambda: str(tmp_path))
        monkeypatch.setattr(uum, "is_valid_game_data_path", lambda p: True)
        monkeypatch.setattr(uum, "slim_init", lambda p: None)
        monkeypatch.setattr(uum, "load_game_resources", lambda: None)
        monkeypatch.setattr(
            uum,
            "process_patch_folder",
            lambda d: {
                "directory": d,
                "patches_found": 0,
                "updated": [],
                "no_units": [],
                "corrupted_files": [],
            },
        )
        patch_dir = tmp_path / "patches"
        patch_dir.mkdir()

        with pytest.raises(SystemExit) as exc:
            uum.run_cli(None, [str(patch_dir)])

        assert exc.value.code == 0
        assert uum.game_resource_path == str(tmp_path)

    def test_reports_error_for_missing_patch_directory(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(uum, "slim_init", lambda p: None)
        monkeypatch.setattr(uum, "load_game_resources", lambda: None)

        with pytest.raises(SystemExit) as exc:
            uum.run_cli(str(tmp_path), [str(tmp_path / "missing")])

        assert exc.value.code == 1
        assert "is not a directory" in capsys.readouterr().err

    def test_exit_code_reflects_corrupted_files(self, monkeypatch, tmp_path):
        monkeypatch.setattr(uum, "slim_init", lambda p: None)
        monkeypatch.setattr(uum, "load_game_resources", lambda: None)
        monkeypatch.setattr(
            uum,
            "process_patch_folder",
            lambda d: {
                "directory": d,
                "patches_found": 1,
                "updated": [],
                "no_units": [],
                "corrupted_files": ["bad.patch_0"],
            },
        )
        patch_dir = tmp_path / "patches"
        patch_dir.mkdir()

        with pytest.raises(SystemExit) as exc:
            uum.run_cli(str(tmp_path), [str(patch_dir)])

        assert exc.value.code == 1


class TestParseArgs:
    def test_parses_game_and_patches(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog", "-g", "C:\\game", "dir1", "dir2"])
        args = uum.parse_args()
        assert args.game == "C:\\game"
        assert args.patches == ["dir1", "dir2"]

    def test_defaults_when_no_args_given(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog"])
        args = uum.parse_args()
        assert args.game is None
        assert args.patches == []


class TestSetupConsoleIo:
    def test_replaces_none_stdout_and_stderr(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "stderr", None)

        uum.setup_console_io()

        assert sys.stdout is not None
        assert sys.stderr is not None

    def test_leaves_existing_stdio_untouched(self, monkeypatch, capsys):
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        uum.setup_console_io()

        assert sys.stdout is original_stdout
        assert sys.stderr is original_stderr


class TestMain:
    def test_dispatches_to_run_cli_when_patches_given(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "argv", ["prog", str(tmp_path)])
        called = {}
        monkeypatch.setattr(
            uum, "run_cli", lambda game_path, patch_dirs: called.setdefault("run_cli", (game_path, patch_dirs))
        )
        monkeypatch.setattr(uum, "run_gui", lambda: called.setdefault("run_gui", True))

        uum.main()

        assert called["run_cli"] == (None, [str(tmp_path)])
        assert "run_gui" not in called

    def test_dispatches_to_run_gui_when_no_args(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog"])
        called = {}
        monkeypatch.setattr(uum, "run_gui", lambda: called.setdefault("run_gui", True))

        uum.main()

        assert called.get("run_gui") is True

    def test_returns_without_running_gui_when_only_game_given(self, monkeypatch, tmp_path):
        (tmp_path / "bundles.nxa").touch()
        monkeypatch.setattr(sys, "argv", ["prog", "-g", str(tmp_path)])
        called = {}
        monkeypatch.setattr(uum, "set_cached_game_data_path", lambda p: called.setdefault("cached", p))
        monkeypatch.setattr(uum, "run_gui", lambda: called.setdefault("run_gui", True))

        uum.main()

        assert "run_gui" not in called
        assert called["cached"] == str(tmp_path)

    def test_exits_with_error_for_invalid_game_path(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(sys, "argv", ["prog", "-g", str(tmp_path)])

        with pytest.raises(SystemExit) as exc:
            uum.main()

        assert exc.value.code == 1
        assert "does not look like a Helldivers II data folder" in capsys.readouterr().err
