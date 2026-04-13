import re


def extract_internal_update_version(name):
    if not name:
        return None
    match = re.search(r"\[v(\d+)\]", str(name or ""), re.IGNORECASE)
    if not match:
        match = re.search(r"(?<![a-z0-9])v(\d+)(?!\.\d)", str(name or ""), re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _expected_semantic_version(expected_version):
    try:
        value = int(expected_version)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return (
        (value >> 16) & 0xFFFF,
        (value >> 8) & 0xFF,
        value & 0xFF,
    )


def _normalize_semantic_version_parts(parts):
    values = [int(part) for part in (parts or [])]
    while len(values) > 3 and values[-1] == 0:
        values.pop()
    if len(values) > 3:
        return None
    while len(values) < 3:
        values.append(0)
    return tuple(values)


def _extract_semantic_versions(name):
    out = []
    for match in re.finditer(r"(?<![a-z0-9])(\d+(?:\.\d+){1,3})(?![a-z0-9])", str(name or ""), re.IGNORECASE):
        try:
            normalized = _normalize_semantic_version_parts(match.group(1).split("."))
        except (TypeError, ValueError):
            normalized = None
        if normalized:
            out.append(normalized)
    return out


def _collect_update_file_versions(file_entries, exclude_russian=False):
    internal_versions = []
    semantic_versions = []
    for entry_id, raw_name in file_entries or []:
        name = str(raw_name or "")
        lowered = name.lower()
        if exclude_russian and ("russian" in lowered or "rus" in lowered):
            continue
        internal_version = extract_internal_update_version(name)
        if internal_version is not None:
            internal_versions.append((internal_version, entry_id))
        for semantic_version in _extract_semantic_versions(name):
            semantic_versions.append((semantic_version, entry_id))
    return internal_versions, semantic_versions


def select_update_entry_ids(file_entries, expected_update_number=None, expected_version=None, exclude_russian=False):
    internal_versions, semantic_versions = _collect_update_file_versions(
        file_entries,
        exclude_russian=exclude_russian,
    )
    expected_value = None
    if expected_version is not None:
        try:
            expected_value = int(expected_version)
        except (TypeError, ValueError):
            expected_value = None
    if expected_value and expected_value > 0:
        exact_internal = [entry_id for version, entry_id in internal_versions if version == expected_value]
        if exact_internal:
            return exact_internal
        expected_semantic = _expected_semantic_version(expected_value)
        if expected_semantic:
            exact_semantic = [entry_id for version, entry_id in semantic_versions if version == expected_semantic]
            if exact_semantic:
                return exact_semantic
    if expected_update_number is not None and expected_update_number > 0:
        exact_update_number = [
            entry_id for version, entry_id in internal_versions
            if (version // 65536) == expected_update_number
        ]
        if exact_update_number:
            return exact_update_number
    if internal_versions:
        highest_internal = max(version for version, _entry_id in internal_versions)
        return [entry_id for version, entry_id in internal_versions if version == highest_internal]
    if semantic_versions:
        highest_semantic = max(version for version, _entry_id in semantic_versions)
        return [entry_id for version, entry_id in semantic_versions if version == highest_semantic]
    return []


def select_update_file_indices(file_names, expected_update_number=None, expected_version=None, exclude_russian=False):
    if not file_names:
        return []
    return select_update_entry_ids(
        list(enumerate(file_names)),
        expected_update_number=expected_update_number,
        expected_version=expected_version,
        exclude_russian=exclude_russian,
    )
