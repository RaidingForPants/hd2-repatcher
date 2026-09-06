import os

import update_unit_mods as uum


class TestIsValidGameDataPath:
    def test_false_when_directory_missing(self, tmp_path):
        assert uum.is_valid_game_data_path(str(tmp_path / "missing")) is False

    def test_false_when_neither_marker_present(self, tmp_path):
        assert uum.is_valid_game_data_path(str(tmp_path)) is False

    def test_true_when_legacy_marker_present(self, tmp_path):
        (tmp_path / uum.LEGACY_MARKER_FILE).touch()
        assert uum.is_valid_game_data_path(str(tmp_path)) is True

    def test_true_when_slim_marker_present(self, tmp_path):
        (tmp_path / uum.SLIM_MARKER_FILE).touch()
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

        assert result.patches_found == 3
        assert result.updated == ["u.patch"]
        assert result.no_units == ["n.patch"]
        assert result.corrupted_files == ["c.patch"]

    def test_empty_patch_list_returns_empty_result(self):
        assert uum.process_patch_files([]) == uum.PatchResult()


class TestProcessPatchFolder:
    def test_includes_directory_and_patch_count(self, tmp_path, monkeypatch):
        (tmp_path / "a.patch_0").touch()
        monkeypatch.setattr(uum, "update_patch_file", lambda p: (uum.UPDATE_SUCCESS, p))

        result = uum.process_patch_folder(str(tmp_path))

        assert result.directory == str(tmp_path)
        assert result.patches_found == 1
        assert len(result.updated) == 1


class TestInitGameResources:
    def test_sets_path_and_loads_resources(self, monkeypatch):
        called = {}
        monkeypatch.setattr(uum, "slim_init", lambda p: called.setdefault("slim_init", p))
        monkeypatch.setattr(uum, "load_game_resources", lambda: called.setdefault("loaded", True))

        uum.init_game_resources("C:\\game\\data")

        assert uum.game_resource_path == "C:\\game\\data"
        assert called == {"slim_init": "C:\\game\\data", "loaded": True}
