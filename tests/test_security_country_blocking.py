import unittest
from unittest.mock import patch

from app.settings import _normalize_security_settings


_IMPORT_ERROR = None
flask_app = None
_block_permanent_blacklist_requests = None
try:
    from app.app import app as flask_app
    from app.app import _block_permanent_blacklist_requests
except ModuleNotFoundError as exc:
    _IMPORT_ERROR = exc


class SecuritySettingsCountryCodeTests(unittest.TestCase):
    def test_normalize_security_settings_normalizes_blocked_country_codes(self):
        normalized = _normalize_security_settings({
            "auth_blocked_country_codes": [" us ", "GB", "us", "123", "G"],
        })
        self.assertEqual(normalized["auth_blocked_country_codes"], ["US", "GB"])

    def test_normalize_security_settings_accepts_csv_and_newlines(self):
        normalized = _normalize_security_settings({
            "auth_blocked_country_codes": "  ca, mx\njp\r\nMX ",
        })
        self.assertEqual(normalized["auth_blocked_country_codes"], ["CA", "MX", "JP"])

    def test_normalize_security_settings_normalizes_allowed_country_codes(self):
        normalized = _normalize_security_settings({
            "auth_allowed_country_codes": [" mt ", "GB", "mt", "123", "G"],
        })
        self.assertEqual(normalized["auth_allowed_country_codes"], ["MT", "GB"])


class CountryBlockingRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if _IMPORT_ERROR is not None:
            raise unittest.SkipTest(f"Missing dependency for country blocking tests: {_IMPORT_ERROR}")

    def test_before_request_blocks_when_country_code_matches_deny_list(self):
        settings = {"security": {"auth_blocked_country_codes": ["US"]}}
        with flask_app.test_request_context(
            "/",
            method="GET",
            environ_base={"REMOTE_ADDR": "203.0.113.42"},
            headers={"User-Agent": "Example Agent"},
        ):
            with (
                patch("app.app.load_settings", return_value=settings),
                patch("app.app._get_auth_protection_config", return_value={"permanent_blacklist": []}),
                patch("app.app._effective_client_ip", return_value="203.0.113.42"),
                patch("app.app._is_permanently_blocked_ip", return_value=False),
                patch("app.app._is_private_ip", return_value=False),
                patch("app.app.lookup_geoip", return_value={"country": "United States", "country_code": "us"}),
                patch("app.app._log_access_dedup") as log_mock,
            ):
                response = _block_permanent_blacklist_requests()

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(log_mock.call_args.kwargs.get("kind"), "country_blocked")
        self.assertEqual(log_mock.call_args.kwargs.get("country_code"), "US")

    def test_before_request_does_not_block_when_country_code_not_in_deny_list(self):
        settings = {"security": {"auth_blocked_country_codes": ["US"]}}
        with flask_app.test_request_context(
            "/",
            method="GET",
            environ_base={"REMOTE_ADDR": "198.51.100.9"},
        ):
            with (
                patch("app.app.load_settings", return_value=settings),
                patch("app.app._get_auth_protection_config", return_value={"permanent_blacklist": []}),
                patch("app.app._effective_client_ip", return_value="198.51.100.9"),
                patch("app.app._is_permanently_blocked_ip", return_value=False),
                patch("app.app._is_private_ip", return_value=False),
                patch("app.app.lookup_geoip", return_value={"country": "Germany", "country_code": "DE"}),
                patch("app.app._log_access_dedup") as log_mock,
            ):
                response = _block_permanent_blacklist_requests()

        self.assertIsNone(response)
        self.assertFalse(log_mock.called)

    def test_before_request_skips_country_lookup_for_private_ip(self):
        settings = {"security": {"auth_blocked_country_codes": ["US"]}}
        with flask_app.test_request_context(
            "/",
            method="GET",
            environ_base={"REMOTE_ADDR": "192.168.1.10"},
        ):
            with (
                patch("app.app.load_settings", return_value=settings),
                patch("app.app._get_auth_protection_config", return_value={"permanent_blacklist": []}),
                patch("app.app._effective_client_ip", return_value="192.168.1.10"),
                patch("app.app._is_permanently_blocked_ip", return_value=False),
                patch("app.app._is_private_ip", return_value=True),
                patch("app.app.lookup_geoip") as geo_mock,
                patch("app.app._log_access_dedup") as log_mock,
            ):
                response = _block_permanent_blacklist_requests()

        self.assertIsNone(response)
        self.assertFalse(geo_mock.called)
        self.assertFalse(log_mock.called)

    def test_before_request_blocks_when_country_not_in_allow_list(self):
        settings = {"security": {"auth_allowed_country_codes": ["US"]}}
        with flask_app.test_request_context(
            "/",
            method="GET",
            environ_base={"REMOTE_ADDR": "203.0.113.44"},
            headers={"User-Agent": "Example Agent"},
        ):
            with (
                patch("app.app.load_settings", return_value=settings),
                patch("app.app._get_auth_protection_config", return_value={"permanent_blacklist": []}),
                patch("app.app._effective_client_ip", return_value="203.0.113.44"),
                patch("app.app._is_permanently_blocked_ip", return_value=False),
                patch("app.app._is_private_ip", return_value=False),
                patch("app.app.lookup_geoip", return_value={"country": "Germany", "country_code": "DE"}),
                patch("app.app._log_access_dedup") as log_mock,
            ):
                response = _block_permanent_blacklist_requests()

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(log_mock.call_args.kwargs.get("kind"), "country_not_whitelisted")
        self.assertEqual(log_mock.call_args.kwargs.get("country_code"), "DE")

    def test_before_request_allows_when_country_in_allow_list(self):
        settings = {"security": {"auth_allowed_country_codes": ["US"]}}
        with flask_app.test_request_context(
            "/",
            method="GET",
            environ_base={"REMOTE_ADDR": "203.0.113.45"},
        ):
            with (
                patch("app.app.load_settings", return_value=settings),
                patch("app.app._get_auth_protection_config", return_value={"permanent_blacklist": []}),
                patch("app.app._effective_client_ip", return_value="203.0.113.45"),
                patch("app.app._is_permanently_blocked_ip", return_value=False),
                patch("app.app._is_private_ip", return_value=False),
                patch("app.app.lookup_geoip", return_value={"country": "United States", "country_code": "US"}),
                patch("app.app._log_access_dedup") as log_mock,
            ):
                response = _block_permanent_blacklist_requests()

        self.assertIsNone(response)
        self.assertFalse(log_mock.called)


if __name__ == "__main__":
    unittest.main()
