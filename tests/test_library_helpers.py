import os
import shutil
import unittest
from collections import namedtuple
from types import SimpleNamespace
from unittest.mock import patch

TEST_TMP_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tmp")

_IMPORT_ERROR = None
flask_app = None
try:
    from app.app import app as flask_app
    from app.app import _app_has_deletable_files
    from app.app import _build_deletable_version_map
    from app.app import _sort_library_rows_by_title_name
    from app.app import manage_delete_library_content
    from app.library import (
        _build_staging_output_path,
        _cleanup_import_staging_roots,
        _delete_target_apps,
        _finalize_staged_conversion_output,
        _format_nsz_command,
        _iter_library_files,
        _pending_cleanup_roots,
        _pending_organize_paths,
        _sanitize_component,
        delete_older_updates,
        delete_library_content,
        delete_orphaned_addons,
        enqueue_cleanup_roots,
        enqueue_organize_paths,
    )
    from app.titles import getDirsAndFiles
except ModuleNotFoundError as exc:
    _IMPORT_ERROR = exc


class LibraryHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"Missing dependency for library helper tests: {_IMPORT_ERROR}")

    class _InvertibleExpr:
        def __invert__(self):
            return self

    @staticmethod
    def _make_app(app_pk, app_id, app_type, version):
        return SimpleNamespace(
            id=app_pk,
            app_id=app_id,
            app_type=app_type,
            app_version=str(version),
            files=[],
        )

    @staticmethod
    def _make_file(file_id, filepath, linked_apps):
        return SimpleNamespace(
            id=file_id,
            filepath=filepath,
            apps=list(linked_apps),
        )

    def _make_test_temp_root(self, name):
        os.makedirs(TEST_TMP_ROOT, exist_ok=True)
        tmp_root = os.path.join(TEST_TMP_ROOT, name)
        shutil.rmtree(tmp_root, ignore_errors=True)
        os.makedirs(tmp_root, exist_ok=True)
        self.addCleanup(shutil.rmtree, tmp_root, ignore_errors=True)
        return tmp_root

    def test_sort_library_rows_by_title_name_uses_visible_title_names(self):
        row_type = namedtuple("LibraryRow", ["title_id", "app_id"])
        rows = [
            row_type(title_id="0100BBBB00000000", app_id="0100BBBB00000000"),
            row_type(title_id="0100AAAA00000000", app_id="0100AAAA00000000"),
            row_type(title_id="0100CCCC00000000", app_id="0100CCCC00000000"),
        ]
        title_name_map = {
            "0100AAAA00000000": "example title z",
            "0100BBBB00000000": "example title m",
            "0100CCCC00000000": "example title a",
        }

        asc_rows = _sort_library_rows_by_title_name(rows, title_name_map, descending=False)
        desc_rows = _sort_library_rows_by_title_name(rows, title_name_map, descending=True)

        self.assertEqual(
            [row.title_id for row in asc_rows],
            ["0100CCCC00000000", "0100BBBB00000000", "0100AAAA00000000"],
        )
        self.assertEqual(
            [row.title_id for row in desc_rows],
            ["0100AAAA00000000", "0100BBBB00000000", "0100CCCC00000000"],
        )

    def test_sanitize_component(self):
        self.assertEqual(_sanitize_component('Game: Name?'), 'Game Name')
        self.assertEqual(_sanitize_component(''), 'Unknown')

    def test_format_nsz_command_threads(self):
        command = _format_nsz_command(
            '{nsz_runner} -C -o "{output_dir}" "{input_file}"',
            'C:\\input.nsp',
            'C:\\output.nsz',
            threads=4
        )
        self.assertIn('-t 4', command)
        self.assertIn('input.nsp', command)

    def test_build_staging_output_path_disabled_returns_final_output(self):
        source = '/library/Game.nsp'
        output = '/library/Game.nsz'
        self.assertEqual(_build_staging_output_path(source, output, ''), output)

    def test_build_staging_output_path_uses_staging_root(self):
        source = '/library/Game.nsp'
        output = '/library/Game.nsz'
        staging = os.path.join(TEST_TMP_ROOT, 'aerofoil-stage')
        staged_output = _build_staging_output_path(source, output, staging)
        self.assertTrue(staged_output.startswith(staging + os.sep))
        self.assertEqual(os.path.basename(staged_output), 'Game.nsz')

    @patch("app.library._resolve_existing_output_path", return_value=None)
    @patch("app.library._cleanup_empty_parent_dirs")
    @patch("app.library.shutil.move")
    def test_finalize_staged_conversion_output_moves_file_to_source_directory(
        self,
        move_mock,
        cleanup_mock,
        existing_output_mock,
    ):
        tmp_root = self._make_test_temp_root('aerofoil_finalize')

        library_dir = os.path.join(tmp_root, 'library')
        staging_root = os.path.join(tmp_root, 'staging')
        os.makedirs(library_dir, exist_ok=True)
        os.makedirs(staging_root, exist_ok=True)

        source_path = os.path.join(library_dir, 'Sample.nsp')
        staged_dir = os.path.join(staging_root, 'run-1')
        os.makedirs(staged_dir, exist_ok=True)
        staged_output = os.path.join(staged_dir, 'Sample.nsz')
        with open(staged_output, 'wb') as handle:
            handle.write(b'nsz-output')

        final_output = _finalize_staged_conversion_output(
            source_path=source_path,
            staged_output_path=staged_output,
            staging_root=staging_root,
        )

        self.assertEqual(final_output, os.path.join(library_dir, 'Sample.nsz'))
        move_mock.assert_called_once_with(staged_output, final_output)
        cleanup_mock.assert_called_once_with(os.path.dirname(staged_output), staging_root)

    def test_finalize_staged_conversion_output_fails_if_final_exists(self):
        tmp_root = self._make_test_temp_root('aerofoil_finalize_exists')

        library_dir = os.path.join(tmp_root, 'library')
        staging_root = os.path.join(tmp_root, 'staging')
        os.makedirs(library_dir, exist_ok=True)
        os.makedirs(staging_root, exist_ok=True)

        source_path = os.path.join(library_dir, 'Sample.nsp')
        existing_final = os.path.join(library_dir, 'Sample.nsz')
        with open(existing_final, 'wb') as handle:
            handle.write(b'existing')

        staged_output = os.path.join(staging_root, 'Sample.nsz')
        with open(staged_output, 'wb') as handle:
            handle.write(b'new-output')

        with self.assertRaises(FileExistsError):
            _finalize_staged_conversion_output(
                source_path=source_path,
                staged_output_path=staged_output,
                staging_root=staging_root,
            )

    @patch("app.library.os.walk")
    @patch("app.library.os.path.isdir", return_value=True)
    @patch("app.library.os.path.isfile", return_value=False)
    def test_enqueue_organize_paths_expands_directories_to_files(self, isfile_mock, isdir_mock, walk_mock):
        walk_mock.return_value = [
            ("X:\\fixture-root\\Example Release NSW-GRP", [], ["game.nsp", "readme.nfo"]),
            ("X:\\fixture-root\\Example Release NSW-GRP\\subdir", [], ["dlc.nsp"]),
        ]
        _pending_organize_paths.clear()
        try:
            enqueue_organize_paths(["X:\\fixture-root\\Example Release NSW-GRP"])
            self.assertEqual(_pending_organize_paths, {
                "X:\\fixture-root\\Example Release NSW-GRP\\game.nsp",
                "X:\\fixture-root\\Example Release NSW-GRP\\readme.nfo",
                "X:\\fixture-root\\Example Release NSW-GRP\\subdir\\dlc.nsp",
            })
        finally:
            _pending_organize_paths.clear()

    @patch("app.library.os.path.isdir", return_value=True)
    def test_enqueue_cleanup_roots_tracks_only_directories(self, isdir_mock):
        _pending_cleanup_roots.clear()
        try:
            enqueue_cleanup_roots(["X:\\fixture-root\\Example Release NSW-GRP"])
            self.assertEqual(_pending_cleanup_roots, {"X:\\fixture-root\\Example Release NSW-GRP"})
        finally:
            _pending_cleanup_roots.clear()

    @patch("app.library.os.rmdir")
    @patch("app.library.os.listdir", return_value=[])
    @patch("app.library.os.remove")
    @patch("app.library.os.walk")
    @patch("app.library.os.path.isdir", return_value=True)
    def test_cleanup_import_staging_roots_removes_only_unsupported_leftovers(
        self,
        isdir_mock,
        walk_mock,
        remove_mock,
        listdir_mock,
        rmdir_mock,
    ):
        walk_mock.return_value = [
            ("X:\\fixture-root\\Example Release NSW-GRP\\subdir", [], ["keep.nsp", "keep-dlc.nsp.hdf", "proof.nfo"]),
            ("X:\\fixture-root\\Example Release NSW-GRP", ["subdir"], ["notes.txt"]),
        ]

        _cleanup_import_staging_roots(["X:\\fixture-root\\Example Release NSW-GRP"])

        self.assertEqual(
            [call.args[0] for call in remove_mock.call_args_list],
            [
                "X:\\fixture-root\\Example Release NSW-GRP\\subdir\\proof.nfo",
                "X:\\fixture-root\\Example Release NSW-GRP\\notes.txt",
            ],
        )

    def test_iter_library_files_includes_wrapped_supported_files(self):
        tmp_root = self._make_test_temp_root("iter_library_files")
        os.makedirs(os.path.join(tmp_root, "subdir"), exist_ok=True)
        with open(os.path.join(tmp_root, "base.nsp.hdf"), "w", encoding="utf-8") as handle:
            handle.write("wrapped")
        with open(os.path.join(tmp_root, "subdir", "update.nsz"), "w", encoding="utf-8") as handle:
            handle.write("native")
        with open(os.path.join(tmp_root, "subdir", "notes.txt"), "w", encoding="utf-8") as handle:
            handle.write("ignored")

        result = sorted(os.path.relpath(path, tmp_root) for path in _iter_library_files(tmp_root))

        self.assertEqual(
            result,
            [
                "base.nsp.hdf",
                os.path.join("subdir", "update.nsz"),
            ],
        )

    def test_get_dirs_and_files_includes_wrapped_supported_files(self):
        tmp_root = self._make_test_temp_root("get_dirs_and_files")
        os.makedirs(os.path.join(tmp_root, "nested"), exist_ok=True)
        with open(os.path.join(tmp_root, "nested", "dlc.nsp.hdf"), "w", encoding="utf-8") as handle:
            handle.write("wrapped")
        with open(os.path.join(tmp_root, "nested", "proof.nfo"), "w", encoding="utf-8") as handle:
            handle.write("ignored")

        dirs, files = getDirsAndFiles(tmp_root)

        self.assertIn(os.path.join(tmp_root, "nested"), dirs)
        self.assertEqual(files, [os.path.join(tmp_root, "nested", "dlc.nsp.hdf")])

    @patch("app.library.delete_file_by_filepath")
    @patch("app.library.os.remove")
    @patch("app.library.os.path.exists", return_value=True)
    def test_delete_target_apps_skips_shared_files_linked_to_non_target_apps(
        self,
        exists_mock,
        remove_mock,
        delete_file_mock,
    ):
        target_app = self._make_app(1, "0100AAAA", "UPDATE", 1)
        foreign_app = self._make_app(2, "0100BBBB", "DLC", 0)
        file_entry = self._make_file(101, "X:\\library\\shared.nsp", [target_app, foreign_app])
        target_app.files = [file_entry]

        result = _delete_target_apps([target_app], dry_run=False, verbose=True)

        self.assertTrue(result["success"])
        self.assertEqual(result["deleted"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertTrue(any("Skip shared file" in line for line in result["details"]))
        remove_mock.assert_not_called()
        delete_file_mock.assert_not_called()

    @patch("app.library.delete_file_by_filepath")
    @patch("app.library.os.remove")
    @patch("app.library.os.path.exists", return_value=False)
    def test_delete_target_apps_cleans_db_when_disk_file_missing(
        self,
        exists_mock,
        remove_mock,
        delete_file_mock,
    ):
        target_app = self._make_app(1, "0100AAAA", "UPDATE", 3)
        file_entry = self._make_file(102, "X:\\library\\missing.nsp", [target_app])
        target_app.files = [file_entry]

        result = _delete_target_apps([target_app], dry_run=False, verbose=True)

        self.assertTrue(result["success"])
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["skipped"], 0)
        remove_mock.assert_not_called()
        delete_file_mock.assert_called_once_with("X:\\library\\missing.nsp")

    def test_delete_library_content_rejects_unknown_scope(self):
        result = delete_library_content("unknown-scope", dry_run=True)

        self.assertFalse(result["success"])
        self.assertTrue(any("Unsupported delete scope" in err for err in result["errors"]))

    @patch("app.library._delete_target_apps", return_value={"success": True, "deleted": 2, "skipped": 0, "mutated": False, "errors": [], "details": []})
    def test_delete_orphaned_addons_uses_targeted_delete_helper(self, delete_targets_mock):
        with flask_app.app_context():
            with patch("app.library.Apps.query") as apps_query_mock, patch("app.library.db.session.query") as session_query_mock:
                session_query_mock.return_value.filter.return_value.exists.return_value = self._InvertibleExpr()
                apps_query_mock.join.return_value.filter.return_value.all.return_value = ["orphan-app"]

                result = delete_orphaned_addons(dry_run=True, verbose=True)

        self.assertTrue(result["success"])
        delete_targets_mock.assert_called_once_with(
            ["orphan-app"],
            dry_run=True,
            verbose=True,
            detail_limit=200,
        )

    @patch("app.library._delete_target_apps")
    def test_delete_older_updates_skips_shared_base_xci(self, delete_targets_mock):
        title = SimpleNamespace(id=1, title_id="01005270232F2000")
        older_update = self._make_app(10, "01005270232F2800", "UPDATE", 1)
        latest_update = self._make_app(11, "01005270232F2800", "UPDATE", 2)
        base_app = self._make_app(12, "01005270232F2000", "BASE", 0)
        shared_file = self._make_file(
            201,
            "X:\\library\\Example Title [01005270232F2000] [BASE][v0].xci",
            [older_update, base_app],
        )
        older_update.files = [shared_file]
        delete_targets_mock.return_value = {
            "success": True,
            "deleted": 0,
            "skipped": 1,
            "mutated": False,
            "errors": [],
            "details": [
                "Skip shared file X:\\library\\Example Title [01005270232F2000] [BASE][v0].xci: linked to non-target apps BASE 01005270232F2000 v0."
            ],
        }

        with flask_app.app_context():
            with patch("app.library.Titles.query") as titles_query_mock, patch("app.library.Apps.query") as apps_query_mock:
                titles_query_mock.all.return_value = [title]
                apps_query_mock.filter_by.return_value.all.return_value = [older_update, latest_update]

                result = delete_older_updates(dry_run=True, verbose=True)

        self.assertTrue(result["success"])
        self.assertEqual(result["deleted"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertTrue(any("Skip shared file" in line for line in result["details"]))
        delete_targets_mock.assert_called_once_with(
            [older_update],
            dry_run=True,
            verbose=True,
            detail_limit=200,
        )

    @patch("app.library.delete_file_by_filepath")
    @patch("app.library.os.remove")
    @patch("app.library.os.path.exists", return_value=True)
    def test_delete_target_apps_marks_mutated_on_success(
        self,
        exists_mock,
        remove_mock,
        delete_file_mock,
    ):
        target_app = self._make_app(1, "0100CCCC", "UPDATE", 5)
        file_entry = self._make_file(103, "X:\\library\\owned.nsp", [target_app])
        target_app.files = [file_entry]

        result = _delete_target_apps([target_app], dry_run=False, verbose=False)

        self.assertTrue(result["mutated"])

    @patch("app.library.delete_file_by_filepath")
    @patch("app.library.os.remove")
    @patch("app.library.os.path.exists", return_value=True)
    def test_delete_target_apps_dry_run_does_not_mark_mutated(
        self,
        exists_mock,
        remove_mock,
        delete_file_mock,
    ):
        target_app = self._make_app(1, "0100DDDD", "UPDATE", 7)
        file_entry = self._make_file(104, "X:\\library\\dryrun.nsp", [target_app])
        target_app.files = [file_entry]

        result = _delete_target_apps([target_app], dry_run=True, verbose=False)

        self.assertFalse(result["mutated"])
        remove_mock.assert_not_called()
        delete_file_mock.assert_not_called()

    def test_app_has_deletable_files_rejects_shared_only_files(self):
        target_app = self._make_app(1, "0100EEEE", "UPDATE", 1)
        foreign_app = self._make_app(2, "0100FFFF", "BASE", 0)
        target_app.files = [self._make_file(105, "X:\\library\\shared.xci", [target_app, foreign_app])]

        self.assertFalse(_app_has_deletable_files(target_app))

    def test_build_deletable_version_map_marks_only_exclusive_owned_versions(self):
        exclusive_app = self._make_app(1, "0100AAAA", "UPDATE", 3)
        exclusive_app.owned = True
        exclusive_app.files = [self._make_file(201, "X:\\library\\owned.nsp", [exclusive_app])]
        shared_app = self._make_app(2, "0100BBBB", "DLC", 1)
        shared_app.owned = True
        foreign_app = self._make_app(3, "0100CCCC", "BASE", 0)
        shared_app.files = [self._make_file(202, "X:\\library\\shared.xci", [shared_app, foreign_app])]

        deletable = _build_deletable_version_map([exclusive_app, shared_app])

        self.assertTrue(deletable[("0100AAAA", "UPDATE", "3")])
        self.assertFalse(deletable[("0100BBBB", "DLC", "1")])

    @patch("app.app._run_post_library_change")
    @patch("app.app.post_library_change")
    @patch("app.app.delete_library_content")
    def test_manage_delete_library_content_uses_sync_post_change(
        self,
        delete_content_mock,
        post_library_change_mock,
        run_post_library_change_mock,
    ):
        delete_content_mock.return_value = {
            "success": True,
            "deleted": 1,
            "skipped": 0,
            "mutated": True,
            "errors": [],
            "details": [],
        }

        with flask_app.test_request_context(
            "/api/manage/delete-library-content",
            method="POST",
            json={"scope": "title_cascade", "title_id": "0100AAAA00000000"},
        ):
            response, status_code = manage_delete_library_content.__wrapped__()

        self.assertEqual(status_code, 200)
        self.assertTrue(response.get_json()["success"])
        run_post_library_change_mock.assert_called_once_with()
        post_library_change_mock.assert_not_called()

    @patch("app.app._run_post_library_change")
    @patch("app.app.delete_library_content")
    def test_manage_delete_library_content_skips_sync_post_change_for_dry_run(
        self,
        delete_content_mock,
        run_post_library_change_mock,
    ):
        delete_content_mock.return_value = {
            "success": True,
            "deleted": 1,
            "skipped": 0,
            "mutated": True,
            "errors": [],
            "details": [],
        }

        with flask_app.test_request_context(
            "/api/manage/delete-library-content",
            method="POST",
            json={"scope": "title_cascade", "title_id": "0100AAAA00000000", "dry_run": True},
        ):
            response, status_code = manage_delete_library_content.__wrapped__()

        self.assertEqual(status_code, 200)
        self.assertTrue(response.get_json()["success"])
        run_post_library_change_mock.assert_not_called()

    @patch("app.app._run_post_library_change")
    @patch("app.app.delete_library_content")
    def test_manage_delete_library_content_skips_sync_post_change_when_not_mutated(
        self,
        delete_content_mock,
        run_post_library_change_mock,
    ):
        delete_content_mock.return_value = {
            "success": False,
            "deleted": 0,
            "skipped": 1,
            "mutated": False,
            "errors": ["Delete failed."],
            "details": [],
        }

        with flask_app.test_request_context(
            "/api/manage/delete-library-content",
            method="POST",
            json={"scope": "title_cascade", "title_id": "0100AAAA00000000"},
        ):
            response, status_code = manage_delete_library_content.__wrapped__()

        self.assertEqual(status_code, 400)
        self.assertFalse(response.get_json()["success"])
        run_post_library_change_mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
