import unittest
from unittest.mock import patch

from app import settings
from app import titles


class TitlesLanguagePreferenceTests(unittest.TestCase):
    def setUp(self):
        titles._reset_titledb_state()
        titles._titles_index_ready = True
        titles._english_titles_index_ready = False
        titles._titles_desc_by_title_id = {}
        titles._titles_images_by_title_id = {}

    def tearDown(self):
        titles._reset_titledb_state()

    def test_get_game_info_prefers_english_metadata_when_enabled(self):
        title_id = "01008EB017F3E000"
        localized_info = {
            'name': 'フィスト 紅蓮城の闇',
            'bannerUrl': 'https://example.invalid/jp-banner.jpg',
            'iconUrl': 'https://example.invalid/jp-icon.jpg',
            'id': title_id,
            'category': 'アクション',
            'nsuId': '111',
            'description': '',
        }
        english_info = {
            'name': 'F.I.S.T.: Forged In Shadow Torch',
            'bannerUrl': 'https://example.invalid/en-banner.jpg',
            'iconUrl': 'https://example.invalid/en-icon.jpg',
            'id': title_id,
            'category': 'Action',
            'nsuId': '222',
            'description': 'English description',
        }
        titles._english_titles_index_ready = True
        titles._titles_images_by_title_id = {
            title_id: ['https://example.invalid/shot-1.jpg']
        }

        with patch(
            'app.titles.load_settings',
            return_value={'titles': {'prefer_english_metadata': True, 'manual_overrides': {}}},
        ), patch(
            'app.titles._get_title_info_from_index',
            return_value=localized_info,
        ), patch(
            'app.titles._get_english_title_info_from_index',
            return_value=english_info,
        ):
            info = titles.get_game_info(title_id)

        self.assertEqual(info['name'], 'F.I.S.T.: Forged In Shadow Torch')
        self.assertEqual(info['category'], 'Action')
        self.assertEqual(info['description'], 'English description')
        self.assertEqual(info['bannerUrl'], 'https://example.invalid/en-banner.jpg')
        self.assertEqual(info['iconUrl'], 'https://example.invalid/en-icon.jpg')
        self.assertEqual(info['nsuId'], '222')
        self.assertEqual(info['screenshots'], ['https://example.invalid/shot-1.jpg'])

    def test_get_game_info_falls_back_to_localized_metadata_when_english_missing(self):
        title_id = "01008EB017F3E000"
        localized_info = {
            'name': 'Localized Title',
            'bannerUrl': 'https://example.invalid/local-banner.jpg',
            'iconUrl': 'https://example.invalid/local-icon.jpg',
            'id': title_id,
            'category': 'Localized Category',
            'nsuId': '111',
            'description': '',
        }
        titles._english_titles_index_ready = True
        titles._titles_desc_by_title_id = {
            title_id: 'Localized fallback description'
        }

        with patch(
            'app.titles.load_settings',
            return_value={'titles': {'prefer_english_metadata': True, 'manual_overrides': {}}},
        ), patch(
            'app.titles._get_title_info_from_index',
            return_value=localized_info,
        ), patch(
            'app.titles._get_english_title_info_from_index',
            return_value=None,
        ):
            info = titles.get_game_info(title_id)

        self.assertEqual(info['name'], 'Localized Title')
        self.assertEqual(info['category'], 'Localized Category')
        self.assertEqual(info['description'], 'Localized fallback description')

    def test_normalize_titles_settings_coerces_prefer_english_metadata(self):
        normalized = settings._normalize_titles_settings({
            'region': 'JP',
            'language': 'ja',
            'prefer_english_metadata': 'true',
            'manual_overrides': [],
        })

        self.assertEqual(normalized['region'], 'JP')
        self.assertEqual(normalized['language'], 'ja')
        self.assertTrue(normalized['prefer_english_metadata'])
        self.assertEqual(normalized['manual_overrides'], {})


if __name__ == '__main__':
    unittest.main()
