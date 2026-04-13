import time

from app.downloads.versioning import select_update_file_indices


TORRENT_UPDATE_SELECTION_ERROR = "No matching update version found in torrent."
NZB_UPDATE_SELECTION_ERROR = "No matching update version found in NZB."
UPDATE_FILE_POLL_ATTEMPTS = 10
UPDATE_FILE_POLL_INTERVAL_SECONDS = 1


def get_matching_update_indices(
    file_names,
    expected_update_number=None,
    expected_version=None,
    exclude_russian=False,
):
    return select_update_file_indices(
        file_names,
        expected_update_number=expected_update_number,
        expected_version=expected_version,
        exclude_russian=exclude_russian,
    )


def preflight_has_matching_update(
    file_names,
    expected_update_number=None,
    expected_version=None,
    exclude_russian=False,
):
    if file_names is None:
        return True
    return bool(
        get_matching_update_indices(
            file_names,
            expected_update_number=expected_update_number,
            expected_version=expected_version,
            exclude_russian=exclude_russian,
        )
    )


def poll_update_file_names(fetch_file_names, attempts=UPDATE_FILE_POLL_ATTEMPTS, sleep_fn=time.sleep):
    for attempt in range(max(int(attempts), 1)):
        file_names = list(fetch_file_names() or [])
        if file_names:
            return file_names
        if attempt + 1 < attempts:
            sleep_fn(UPDATE_FILE_POLL_INTERVAL_SECONDS)
    return []
