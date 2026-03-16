import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.file_watcher import Handler


class FileWatcherTests(unittest.TestCase):
    @patch("app.file_watcher.os.path.getsize", return_value=10)
    def test_collect_event_tracks_wrapped_supported_file(self, getsize_mock):
        callback_events = []
        handler = Handler(callback_events.extend, stability_duration=5)
        handler.debounced_check_final = lambda: None
        with patch.object(handler, "_check_file_stability") as check_mock:
            handler.collect_event(
                SimpleNamespace(
                    is_directory=False,
                    event_type="created",
                    src_path="X:\\library\\Example DLC.nsp.hdf",
                    dest_path="X:\\library\\Example DLC.nsp.hdf",
                ),
                "X:\\library",
            )

        self.assertIn("X:\\library\\Example DLC.nsp.hdf", handler.tracked_files)
        check_mock.assert_called_once()

    def test_collect_event_treats_wrapped_move_to_unsupported_path_as_delete(self):
        callback_events = []
        handler = Handler(callback_events.extend, stability_duration=5)
        handler.debounced_check_final = lambda: None
        with patch.object(handler, "_check_file_stability") as check_mock:
            handler.collect_event(
                SimpleNamespace(
                    is_directory=False,
                    event_type="moved",
                    src_path="X:\\library\\Example DLC.nsp.hdf",
                    dest_path="X:\\library\\Example DLC.txt",
                ),
                "X:\\library",
            )

        self.assertEqual(len(callback_events), 1)
        self.assertEqual(callback_events[0].type, "deleted")
        check_mock.assert_called_once()
