import copy
import time
import unittest


_IMPORT_ERROR = None
flask_app = None
_prune_stale_active_transfers = None
_active_transfers = None
_active_transfers_lock = None
try:
    from app.app import (
        app as flask_app,
        _prune_stale_active_transfers,
        _active_transfers,
        _active_transfers_lock,
    )
except ModuleNotFoundError as exc:
    _IMPORT_ERROR = exc


class ActivityMonitorCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"Missing dependency for activity monitor tests: {_IMPORT_ERROR}")

    def setUp(self):
        with _active_transfers_lock:
            self.original_active_transfers = copy.deepcopy(_active_transfers)

    def tearDown(self):
        with _active_transfers_lock:
            _active_transfers.clear()
            _active_transfers.update(copy.deepcopy(self.original_active_transfers))

    def test_prune_stale_active_transfers_removes_old_entries(self):
        now = time.time()
        with _active_transfers_lock:
            _active_transfers.clear()
            _active_transfers.update({
                'stale-transfer': {
                    'id': 'stale-transfer',
                    'started_at': now - 900,
                    'last_seen_at': now - 600,
                    'filename': 'stale.nsp',
                },
                'fresh-transfer': {
                    'id': 'fresh-transfer',
                    'started_at': now - 20,
                    'last_seen_at': now - 5,
                    'filename': 'fresh.nsp',
                },
            })

        removed = _prune_stale_active_transfers(now=now, stale_after_s=300)

        self.assertEqual(removed, ['stale-transfer'])
        with _active_transfers_lock:
            self.assertNotIn('stale-transfer', _active_transfers)
            self.assertIn('fresh-transfer', _active_transfers)


if __name__ == '__main__':
    unittest.main()
