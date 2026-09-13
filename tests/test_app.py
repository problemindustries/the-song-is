import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile


APP_PATH = Path(__file__).parents[1] / "app" / "app.py"
SPEC = importlib.util.spec_from_file_location("the_song_is_app", APP_PATH)
APP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APP)


class ProjectLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_file = self.root / "data.json"
        self.data_patch = mock.patch.object(APP, "DATA_FILE", str(self.data_file))
        self.data_patch.start()

    def tearDown(self):
        self.data_patch.stop()
        self.temp_dir.cleanup()

    def write_data(self, data):
        self.data_file.write_text(json.dumps(data))

    def make_flp_project(self, library, name):
        folder = library / name
        folder.mkdir(parents=True)
        (folder / f"{name}.flp").write_bytes(b"FL Studio project")

    def make_zip_project(self, path, flp_name="Song.flp"):
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(flp_name, b"FL Studio project")

    def test_legacy_single_folder_is_exposed_as_folder_list(self):
        library = self.root / "Legacy Library"
        library.mkdir()
        self.write_data({"_daw": "fl_studio", "_projects_dir": str(library)})

        config = APP.Api().get_config()

        self.assertTrue(config["is_configured"])
        self.assertEqual(config["projects_dirs"], [str(library)])
        self.assertEqual(config["projects_dir"], str(library))

    def test_set_config_writes_new_and_legacy_folder_keys(self):
        first = self.root / "First"
        second = self.root / "Second"
        first.mkdir()
        second.mkdir()

        result = APP.Api().set_config("reaper", [str(first), str(second), str(first)])
        saved = json.loads(self.data_file.read_text())

        self.assertEqual(result, {"ok": True})
        self.assertEqual(saved["_projects_dirs"], [str(first), str(second)])
        self.assertEqual(saved["_projects_dir"], str(first))

    def test_scans_multiple_folders_and_keeps_duplicate_names_stable(self):
        first = self.root / "First"
        second = self.root / "Second"
        first.mkdir()
        second.mkdir()
        self.make_flp_project(first, "Shared")
        self.make_flp_project(second, "Shared")
        (second / "Loose.flp").write_bytes(b"FL Studio project")
        self.make_zip_project(second / "Packed.zip", "Packed.flp")
        with zipfile.ZipFile(second / "Samples.zip", "w") as archive:
            archive.writestr("kick.wav", b"sample")
        self.write_data({
            "_daw": "fl_studio",
            "_projects_dir": str(first),
            "_projects_dirs": [str(first), str(second)],
        })

        first_scan = APP.Api().get_projects()
        first_names = {project["name"] for project in first_scan}
        self.assertEqual(first_names, {"Shared", "Shared — Second", "Loose", "Packed"})
        self.assertNotIn("Samples", first_names)
        for project in first_scan:
            self.assertIn("created_at", project)
            self.assertIsNotNone(project["modified_at"])
            self.assertEqual(project["mtime"], project["modified_at"])

        data = json.loads(self.data_file.read_text())
        data["_projects_dirs"] = [str(second), str(first)]
        self.write_data(data)
        second_names = {project["name"] for project in APP.Api().get_projects()}
        self.assertEqual(second_names, first_names)

    def test_fl_zip_is_opened_explicitly_with_fl_studio_on_macos(self):
        project = self.root / "Packed.zip"
        self.make_zip_project(project)

        with mock.patch.object(APP.platform, "system", return_value="Darwin"), \
             mock.patch.object(APP.subprocess, "Popen") as popen:
            result = APP.Api().open_file(str(project), "fl_studio")

        self.assertEqual(result, {"ok": True})
        popen.assert_called_once_with(["open", "-a", "FL Studio", str(project)])

    def test_preview_audio_inside_project_uses_portable_relative_path(self):
        project = self.root / "Project"
        export = project / "Exports" / "mix.wav"
        export.parent.mkdir(parents=True)
        export.write_bytes(b"audio")

        reference = APP.preview_audio_reference(str(export), str(project))
        resolved = APP.resolve_preview_audio(str(project), reference)

        self.assertEqual(reference, {"path": os.path.join("Exports", "mix.wav"), "relative": True})
        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["path"], os.path.realpath(export))
        self.assertTrue(resolved["url"].startswith("file:"))

    def test_preview_audio_outside_project_uses_absolute_path(self):
        project = self.root / "Project"
        project.mkdir()
        export = self.root / "Master.mp3"
        export.write_bytes(b"audio")

        reference = APP.preview_audio_reference(str(export), str(project))

        self.assertEqual(reference, {"path": os.path.realpath(export), "relative": False})
        self.assertTrue(APP.resolve_preview_audio(str(project), reference)["ok"])

    def test_preview_audio_rejects_unsupported_or_missing_files(self):
        project = self.root / "Project"
        project.mkdir()
        unsupported = project / "mix.aiff"
        unsupported.write_bytes(b"audio")

        unsupported_result = APP.resolve_preview_audio(
            str(project), {"path": "mix.aiff", "relative": True}
        )
        missing_result = APP.resolve_preview_audio(
            str(project), {"path": "missing.wav", "relative": True}
        )

        self.assertEqual(unsupported_result["error"], "Unsupported preview audio format")
        self.assertEqual(missing_result["error"], "Preview audio file not found")

    def test_assign_preview_audio_reuses_safe_relative_reference(self):
        project = self.root / "Project"
        project.mkdir()
        export = project / "mix.wav"
        export.write_bytes(b"audio")

        result = APP.Api().assign_audio_file(str(project), str(export))

        self.assertTrue(result["ok"])
        self.assertEqual(result["reference"], {"path": "mix.wav", "relative": True})

    def test_audio_picker_opens_in_project_folder_on_macos(self):
        project_file = self.root / "Song.flp"
        project_file.write_bytes(b"project")

        with mock.patch.object(APP.platform, "system", return_value="Darwin"), \
             mock.patch.object(APP.subprocess, "run") as run:
            run.return_value.stdout = ""
            result = APP.Api().browse_audio_file(str(project_file))

        script = run.call_args.args[0][2]
        self.assertEqual(result, {"cancelled": True})
        self.assertIn("default location POSIX file", script)
        self.assertIn(str(self.root), script)


if __name__ == "__main__":
    unittest.main()
