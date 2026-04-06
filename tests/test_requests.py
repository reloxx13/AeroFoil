import unittest
import datetime
from types import SimpleNamespace
from unittest.mock import patch

_IMPORT_ERROR = None
flask_app = None
create_title_request_api = None
list_requests_api = None
try:
    from app.app import app as flask_app
    from app.app import create_title_request_api
    from app.app import list_requests_api
except ModuleNotFoundError as exc:
    _IMPORT_ERROR = exc


class _FakeUser:
    def __init__(self, user_id=1, is_admin=True):
        self.id = user_id
        self.is_admin = is_admin
        self.is_authenticated = True

    def has_access(self, access):
        return access in {"shop", "admin", "backup"}


class RequestFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"Missing dependency for request tests: {_IMPORT_ERROR}")

    def _invoke_create_request(self, payload, create_result=None):
        fake_user = _FakeUser(user_id=17, is_admin=True)
        with flask_app.test_request_context("/api/requests", method="POST", json=payload):
            with patch("app.auth.admin_account_created", return_value=True), patch("app.auth.current_user", fake_user), patch("app.app.current_user", fake_user):
                if create_result is None:
                    response = create_title_request_api()
                    create_mock = None
                else:
                    with patch("app.app.create_title_request", return_value=create_result) as create_mock:
                        response = create_title_request_api()

        if isinstance(response, tuple):
            response, status_code = response
        else:
            status_code = response.status_code
        return response.get_json(), status_code, create_mock

    def test_create_request_api_accepts_manual_title_id_without_name(self):
        data, status_code, create_mock = self._invoke_create_request(
            {"title_id": "0100B6E012EBE000"},
            (True, "Request created.", SimpleNamespace(id=31)),
        )

        self.assertEqual(status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["request_id"], 31)
        self.assertEqual(data["message"], "Request created.")
        create_mock.assert_called_once_with(17, "0100B6E012EBE000", title_name=None)

    def test_create_request_api_accepts_manual_title_id_with_name(self):
        data, status_code, create_mock = self._invoke_create_request(
            {"title_id": "0100C62011050000", "title_name": "Example Title"},
            (True, "Request created.", SimpleNamespace(id=44)),
        )

        self.assertEqual(status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["request_id"], 44)
        create_mock.assert_called_once_with(17, "0100C62011050000", title_name="Example Title")

    def test_create_request_api_is_idempotent_for_duplicate_open_request(self):
        data, status_code, create_mock = self._invoke_create_request(
            {"title_id": "0100C62011050000", "title_name": "Example Title"},
            (True, "Request already exists.", SimpleNamespace(id=44)),
        )

        self.assertEqual(status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Request already exists.")
        self.assertEqual(data["request_id"], 44)
        create_mock.assert_called_once_with(17, "0100C62011050000", title_name="Example Title")

    def test_create_request_api_rejects_invalid_title_id(self):
        data, status_code, create_mock = self._invoke_create_request({"title_id": "1234"})

        self.assertEqual(status_code, 400)
        self.assertFalse(data["success"])
        self.assertEqual(data["message"], "Title ID must be 16 characters")
        self.assertIsNone(create_mock)


class RequestListApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"Missing dependency for request tests: {_IMPORT_ERROR}")

    def test_list_requests_api_rejects_non_admin_all_requests_view(self):
        fake_user = _FakeUser(user_id=17, is_admin=False)

        with flask_app.test_request_context("/api/requests?all=1", method="GET"):
            with (
                patch("app.auth.admin_account_created", return_value=True),
                patch("app.auth.current_user", fake_user),
                patch("app.app.current_user", fake_user),
                patch("app.app.list_requests") as list_mock,
            ):
                response, status_code = list_requests_api()

        self.assertEqual(status_code, 403)
        self.assertFalse(response.get_json()["success"])
        list_mock.assert_not_called()

    def test_list_requests_api_auto_closes_open_requests_when_title_is_now_in_library(self):
        fake_user = _FakeUser(user_id=17, is_admin=True)
        request_row = SimpleNamespace(
            id=31,
            created_at=datetime.datetime(2026, 1, 2, 3, 4, 5),
            status="open",
            title_id="0100B6E012EBE000",
            title_name="Example Title",
            user=SimpleNamespace(id=17, user="alice"),
        )
        titles_query = SimpleNamespace()
        titles_query.filter = lambda *args, **kwargs: titles_query
        titles_query.all = lambda: [SimpleNamespace(title_id="0100B6E012EBE000")]
        update_query = SimpleNamespace()
        update_query.filter = lambda *args, **kwargs: update_query
        update_query.update = lambda *args, **kwargs: 1

        with flask_app.test_request_context("/api/requests?all=1", method="GET"):
            with (
                patch("app.auth.admin_account_created", return_value=True),
                patch("app.auth.current_user", fake_user),
                patch("app.app.current_user", fake_user),
                patch("app.app.list_requests", return_value=[request_row]),
                patch("app.app.db.session.query", side_effect=[titles_query, update_query]),
                patch("app.app.db.session.commit") as commit_mock,
            ):
                response = list_requests_api()

        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(len(payload["requests"]), 1)
        self.assertEqual(payload["requests"][0]["status"], "closed")
        self.assertEqual(payload["requests"][0]["user"]["user"], "alice")
        commit_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
