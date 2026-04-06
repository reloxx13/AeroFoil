import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


_IMPORT_ERROR = None
flask_app = None
get_user_history = None
try:
    from app.app import app as flask_app
    from app.auth import get_user_history
except ModuleNotFoundError as exc:
    _IMPORT_ERROR = exc


class UserHistoryApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"Missing dependency for user history tests: {_IMPORT_ERROR}")

    def test_get_user_history_returns_transfer_rows_for_admin(self):
        user_row = SimpleNamespace(id=7, user='alice')
        fake_user_query = MagicMock()
        fake_query = MagicMock()
        fake_query.first.return_value = user_row
        fake_user_query.filter_by.return_value = fake_query
        history_rows = [
            {
                'at': 1710000000,
                'kind': 'transfer',
                'user': 'alice',
                'remote_addr': '203.0.113.9',
                'title_id': '0100ABCD',
                'filename': 'Example Title [0100ABCD][v1].nsp',
                'bytes_sent': 12345,
                'ok': True,
                'status_code': 200,
            }
        ]
        fake_current_user = SimpleNamespace(is_authenticated=True, has_access=lambda access: access == 'admin')

        with flask_app.test_request_context('/api/admin/user-history/7?limit=25', method='GET'):
            with (
                patch('app.auth.admin_account_created', return_value=True),
                patch('app.auth.current_user', fake_current_user),
                patch('app.auth.User.query', fake_user_query),
                patch('app.auth.get_access_events', return_value=history_rows) as events_mock,
                patch('app.titles.titledb_session') as titledb_session_mock,
                patch('app.titles.get_game_info', return_value={'name': 'Example Title'}),
            ):
                titledb_session_mock.return_value.__enter__.return_value = True
                titledb_session_mock.return_value.__exit__.return_value = False
                response = get_user_history(7)

        payload = response.get_json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['user']['user'], 'alice')
        self.assertEqual(payload['summary']['downloads'], 1)
        self.assertEqual(payload['summary']['unique_titles'], 1)
        self.assertEqual(payload['summary']['unique_ips'], 1)
        self.assertEqual(payload['history'][0]['title_name'], 'Example Title')
        events_mock.assert_called_once_with(limit=25, kinds=['transfer'], user='alice')

    def test_get_user_history_clamps_limit_and_tolerates_title_lookup_errors(self):
        user_row = SimpleNamespace(id=7, user='alice')
        fake_user_query = MagicMock()
        fake_query = MagicMock()
        fake_query.first.return_value = user_row
        fake_user_query.filter_by.return_value = fake_query
        history_rows = [
            {
                'at': 1710000000,
                'kind': 'transfer',
                'user': 'alice',
                'remote_addr': '203.0.113.9',
                'title_id': '0100ABCD',
                'filename': 'Example Title [0100ABCD][v1].nsp',
                'bytes_sent': 12345,
                'ok': True,
                'status_code': 200,
            }
        ]
        fake_current_user = SimpleNamespace(is_authenticated=True, has_access=lambda access: access == 'admin')

        with flask_app.test_request_context('/api/admin/user-history/7?limit=9999', method='GET'):
            with (
                patch('app.auth.admin_account_created', return_value=True),
                patch('app.auth.current_user', fake_current_user),
                patch('app.auth.User.query', fake_user_query),
                patch('app.auth.get_access_events', return_value=history_rows) as events_mock,
                patch('app.titles.titledb_session') as titledb_session_mock,
                patch('app.titles.get_game_info', side_effect=RuntimeError('titledb unavailable')),
            ):
                titledb_session_mock.return_value.__enter__.return_value = True
                titledb_session_mock.return_value.__exit__.return_value = False
                response = get_user_history(7)

        payload = response.get_json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['summary']['downloads'], 1)
        self.assertEqual(payload['summary']['total_bytes'], 12345)
        self.assertNotIn('title_name', payload['history'][0])
        events_mock.assert_called_once_with(limit=500, kinds=['transfer'], user='alice')

    def test_get_user_history_returns_404_for_unknown_user(self):
        fake_user_query = MagicMock()
        fake_query = MagicMock()
        fake_query.first.return_value = None
        fake_user_query.filter_by.return_value = fake_query
        fake_current_user = SimpleNamespace(is_authenticated=True, has_access=lambda access: access == 'admin')

        with flask_app.test_request_context('/api/admin/user-history/999', method='GET'):
            with (
                patch('app.auth.admin_account_created', return_value=True),
                patch('app.auth.current_user', fake_current_user),
                patch('app.auth.User.query', fake_user_query),
            ):
                response, status_code = get_user_history(999)

        self.assertEqual(status_code, 404)
        payload = response.get_json()
        self.assertFalse(payload['success'])
        self.assertEqual(payload['error'], 'User not found.')


if __name__ == '__main__':
    unittest.main()
