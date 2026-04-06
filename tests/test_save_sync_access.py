import unittest
from unittest.mock import patch


_IMPORT_ERROR = None
flask_app = None
_resolve_save_sync_user = None
delete_save_api = None
try:
    from app.app import app as flask_app
    from app.app import _resolve_save_sync_user
    from app.app import delete_save_api
except ModuleNotFoundError as exc:
    _IMPORT_ERROR = exc


class _FakeSaveUser:
    def __init__(
        self,
        *,
        username="example-user",
        authenticated=True,
        frozen=False,
        frozen_message="",
        shop_access=True,
        backup_access=True,
    ):
        self.user = username
        self.is_authenticated = authenticated
        self.frozen = frozen
        self.frozen_message = frozen_message
        self.shop_access = shop_access
        self.backup_access = backup_access
        self.password = "stored-password-hash"

    def has_shop_access(self):
        return bool(self.shop_access) and not bool(self.frozen)


class SaveSyncAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"Missing dependency for save sync tests: {_IMPORT_ERROR}")

    def test_resolve_save_sync_user_rejects_frozen_authenticated_session(self):
        fake_user = _FakeSaveUser(frozen=True, frozen_message="Account frozen by admin.")

        with flask_app.test_request_context("/api/saves/delete/0100B6E012EBE000", method="DELETE"):
            with patch("app.app.current_user", fake_user):
                user, error, status = _resolve_save_sync_user()

        self.assertIsNone(user)
        self.assertEqual(error, "Account frozen by admin.")
        self.assertEqual(status, 403)

    def test_resolve_save_sync_user_requires_shop_access_for_authenticated_session(self):
        fake_user = _FakeSaveUser(shop_access=False, backup_access=True)

        with flask_app.test_request_context("/api/saves/delete/0100B6E012EBE000", method="DELETE"):
            with patch("app.app.current_user", fake_user):
                user, error, status = _resolve_save_sync_user()

        self.assertIsNone(user)
        self.assertEqual(error, 'User "example-user" does not have access to the shop.')
        self.assertEqual(status, 403)

    def test_resolve_save_sync_user_requires_backup_access_for_authenticated_session(self):
        fake_user = _FakeSaveUser(shop_access=True, backup_access=False)

        with flask_app.test_request_context("/api/saves/delete/0100B6E012EBE000", method="DELETE"):
            with patch("app.app.current_user", fake_user):
                user, error, status = _resolve_save_sync_user()

        self.assertIsNone(user)
        self.assertEqual(error, "Backup access is required for save sync.")
        self.assertEqual(status, 403)

    def test_resolve_save_sync_user_accepts_basic_auth_when_session_is_not_authenticated(self):
        session_user = _FakeSaveUser(authenticated=False)
        stored_user = _FakeSaveUser(username="basic-user", authenticated=False, shop_access=True, backup_access=True)
        fake_query = type("FakeQuery", (), {"first": staticmethod(lambda: stored_user)})()
        fake_user_model = type("FakeUserModel", (), {"query": type("FakeUserQuery", (), {"filter_by": staticmethod(lambda **kwargs: fake_query)})()})()

        with flask_app.test_request_context(
            "/api/saves/delete/0100B6E012EBE000",
            method="DELETE",
            headers={"Authorization": "Basic YmFzaWMtdXNlcjpzZWNyZXQ="},
        ):
            with (
                patch("app.app.current_user", session_user),
                patch("app.app.User", fake_user_model),
                patch("app.app.check_password_hash", return_value=True),
            ):
                user, error, status = _resolve_save_sync_user()

        self.assertIs(user, stored_user)
        self.assertIsNone(error)
        self.assertIsNone(status)

    def test_delete_save_api_returns_403_for_frozen_authenticated_session(self):
        fake_user = _FakeSaveUser(frozen=True, frozen_message="Account is frozen.")

        with flask_app.test_request_context("/api/saves/delete/0100B6E012EBE000", method="DELETE"):
            with patch("app.app.current_user", fake_user):
                response, status_code = delete_save_api("0100B6E012EBE000")

        self.assertEqual(status_code, 403)
        self.assertEqual(response.get_json()["message"], "Account is frozen.")


if __name__ == "__main__":
    unittest.main()
