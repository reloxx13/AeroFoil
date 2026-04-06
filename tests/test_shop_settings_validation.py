import unittest

from app.settings import _normalize_shop_settings, verify_settings
from app.shop import TINFOIL_PUBLIC_KEY


class ShopSettingsValidationTests(unittest.TestCase):
    def test_tinfoil_only_mode_forces_encrypt(self):
        normalized = _normalize_shop_settings({
            'encrypt': False,
            'tinfoil_only_mode': True,
        })
        self.assertTrue(normalized['tinfoil_only_mode'])
        self.assertTrue(normalized['encrypt'])

    def test_verify_shop_settings_accepts_default_public_key(self):
        success, errors = verify_settings('shop', {
            'encrypt': True,
            'public_key': TINFOIL_PUBLIC_KEY,
        })
        self.assertTrue(success)
        self.assertEqual(errors, [])

    def test_verify_shop_settings_accepts_blank_public_key(self):
        success, errors = verify_settings('shop', {
            'encrypt': True,
            'public_key': '',
        })
        self.assertTrue(success)
        self.assertEqual(errors, [])

    def test_verify_shop_settings_rejects_invalid_public_key(self):
        success, errors = verify_settings('shop', {
            'encrypt': True,
            'public_key': 'not-a-valid-pem',
        })
        self.assertFalse(success)
        self.assertTrue(any(err.get('path') == 'shop/public_key' for err in errors))


if __name__ == '__main__':
    unittest.main()
