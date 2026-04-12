import os
import shutil
import stat
import unittest
from unittest.mock import patch

from app.settings import _normalize_library_naming_templates, verify_settings

TEST_TMP_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".tmp", "library-settings-tests")


class LibrarySettingsValidationTests(unittest.TestCase):
    def setUp(self):
        os.makedirs(TEST_TMP_ROOT, exist_ok=True)
        case_name = self.id().rsplit('.', 1)[-1]
        self.tmp_root = os.path.join(TEST_TMP_ROOT, case_name)
        shutil.rmtree(self.tmp_root, ignore_errors=True)
        os.makedirs(self.tmp_root, exist_ok=True)
        self.library_path = os.path.join(self.tmp_root, 'library')
        self.staging_path = os.path.join(self.tmp_root, 'staging')
        os.makedirs(self.library_path, exist_ok=True)
        os.makedirs(self.staging_path, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _base_payload(self):
        return {
            'paths': [self.library_path],
            'conversion_staging_dir': self.staging_path,
        }

    def test_library_settings_accept_valid_staging_directory(self):
        success, errors = verify_settings('library', self._base_payload())
        self.assertTrue(success)
        self.assertEqual(errors, [])

    def test_library_settings_reject_relative_staging_directory(self):
        payload = self._base_payload()
        payload['conversion_staging_dir'] = 'relative/staging'
        success, errors = verify_settings('library', payload)
        self.assertFalse(success)
        self.assertTrue(any(err.get('path') == 'library/conversion_staging_dir' for err in errors))

    def test_library_settings_reject_staging_directory_inside_library(self):
        payload = self._base_payload()
        payload['conversion_staging_dir'] = os.path.join(self.library_path, 'staging')
        os.makedirs(payload['conversion_staging_dir'], exist_ok=True)
        success, errors = verify_settings('library', payload)
        self.assertFalse(success)
        self.assertTrue(any('must not be inside' in (err.get('error') or '') for err in errors))

    def test_library_settings_reject_missing_staging_directory(self):
        payload = self._base_payload()
        payload['conversion_staging_dir'] = os.path.join(self.tmp_root, 'does-not-exist')
        success, errors = verify_settings('library', payload)
        self.assertFalse(success)
        self.assertTrue(any('does not exist' in (err.get('error') or '') for err in errors))

    def test_library_settings_reject_non_writable_staging_directory(self):
        payload = self._base_payload()
        readonly_dir = os.path.join(self.tmp_root, 'readonly')
        os.makedirs(readonly_dir, exist_ok=True)
        original_mode = stat.S_IMODE(os.stat(readonly_dir).st_mode)
        with patch("app.settings.os.access", return_value=False):
            try:
                os.chmod(readonly_dir, 0o555)
                payload['conversion_staging_dir'] = readonly_dir
                success, errors = verify_settings('library', payload)
            finally:
                os.chmod(readonly_dir, original_mode)
        self.assertFalse(success)
        self.assertTrue(any('not writable' in (err.get('error') or '') for err in errors))

    def test_library_settings_can_skip_library_path_existence_validation(self):
        payload = self._base_payload()
        payload['paths'] = [os.path.join(self.tmp_root, 'missing-library')]
        payload['_validate_paths'] = False
        success, errors = verify_settings('library', payload)
        self.assertTrue(success)
        self.assertEqual(errors, [])

    def test_library_naming_templates_fix_legacy_update_filename_token(self):
        normalized = _normalize_library_naming_templates({
            'active': 'flat',
            'templates': {
                'flat': {
                    'base': {
                        'folder': '.',
                        'filename': '{title} [{title_id}] [BASE][v{version}].{ext}',
                    },
                    'update': {
                        'folder': '.',
                        'filename': '{title} [{title_id}] [UPDATE][v{version}].{ext}',
                    },
                    'dlc': {
                        'folder': '.',
                        'filename': '{title} - {dlc_name} [{app_id}] [DLC][v{version}].{ext}',
                    },
                    'other': {
                        'folder': '.',
                        'filename': '{title} [{title_id}] [UNKNOWN].{ext}',
                    },
                },
            },
        })

        self.assertEqual(
            normalized['templates']['flat']['update']['filename'],
            '{title} [{app_id}] [UPDATE][v{version}].{ext}',
        )


if __name__ == '__main__':
    unittest.main()
