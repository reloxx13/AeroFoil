import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DownloadTemplateRegressionTests(unittest.TestCase):
    def test_index_download_search_rows_use_safe_dom_construction(self):
        content = (REPO_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")

        self.assertIn("function buildDownloadSearchRow(item, actionLabel, extraData = {}) {", content)
        self.assertIn("function formatPublishedAtTooltip(publishedAt) {", content)
        self.assertIn("function renderDownloadSearchResults(result, actionLabel, buildExtraData) {", content)
        self.assertIn("function runDetailsDownloadSearch({ button, statusMessage = 'Searching Prowlarr...', request, actionLabel, buildExtraData }) {", content)
        self.assertIn("const row = $('<tr></tr>');", content)
        self.assertIn("row.append($('<td></td>').text(item?.title || '-'));", content)
        self.assertIn("row.append($('<td></td>').text(item?.indexer || '-'));", content)
        self.assertIn("const ageTooltip = formatPublishedAtTooltip(item?.published_at);", content)
        self.assertIn("button.attr('data-download-url', String(item?.download_url || ''));", content)
        self.assertIn("renderDownloadSearchResults(result, actionLabel, buildExtraData);", content)
        self.assertNotIn("return `<tr>${cells.join('')}</tr>`;", content)
        self.assertNotIn('data-download-url="${item.download_url || \'\'}"', content)

    def test_index_download_search_handlers_route_through_shared_helper(self):
        content = (REPO_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")

        self.assertEqual(content.count("runDetailsDownloadSearch({"), 5)
        self.assertIn("statusMessage: `Searching Prowlarr for ${label}...`,", content)
        self.assertIn("bootstrap.Modal.getOrCreateInstance(document.getElementById('torrentSearchModal')).show();", content)

    def test_discovery_tiles_prefer_title_names_over_ids(self):
        content = (REPO_ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")

        self.assertIn(
            "const baseTitle = String((game && (game.title_id_name || game.title_name || game.name || game.title_id || game.app_id)) || '').trim();",
            content,
        )
        self.assertIn(
            "const contentTitle = String((game && (game.name || game.title_name || game.app_id || game.title_id)) || '').trim();",
            content,
        )

    def test_active_download_rows_use_safe_dom_construction(self):
        content = (REPO_ROOT / "app" / "templates" / "downloads.html").read_text(encoding="utf-8")

        self.assertIn("function loadActiveDownloads() {", content)
        self.assertIn("{% if download_ui_visibility.show_torrent_columns %}\n                                                <th>Down</th>\n                                                <th>Up</th>", content)
        self.assertIn("const activeDownloadsColumnCount = 7", content)
        self.assertIn("const row = $('<tr></tr>');", content)
        self.assertIn("row.append($('<td class=\"small\"></td>').text((item['name'] || '').toString()));", content)
        self.assertIn("row.append($('<td class=\"small text-muted\"></td>').text((item['status'] || '').toString()));", content)
        self.assertIn("if (downloadUiVisibility.show_torrent_columns) {\n                    row.append($('<td class=\"small\"></td>').text(formatSpeed(item['down_speed'])));", content)
        self.assertIn("body.append(row);", content)
        self.assertNotIn("const row = $(`<tr>${cells.join('')}</tr>`);", content)
        self.assertNotIn("`<td class=\"small\">${(item['name'] || '').toString()}</td>`", content)

    def test_queue_rows_use_safe_dom_construction_and_delete_api(self):
        content = (REPO_ROOT / "app" / "templates" / "downloads.html").read_text(encoding="utf-8")

        self.assertIn("function loadQueueState() {", content)
        self.assertIn("const row = $('<tr></tr>');", content)
        self.assertIn("row.append($('<td class=\"small\"></td>').text((item['label'] || 'Manual download').toString()));", content)
        self.assertIn("function deleteQueuedDownload(key, button) {", content)
        self.assertIn("url: '/api/downloads/queue/delete',", content)
        self.assertNotIn("$('#downloadsQueueList').text(lines.join('\\n'));", content)


if __name__ == "__main__":
    unittest.main()
