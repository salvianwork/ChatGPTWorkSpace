"""Review-only regional candidates. These rules never assign a target ID."""
import difflib
import json
from pathlib import Path
import re
import unicodedata


def normalize(value, level):
    value = unicodedata.normalize('NFKC', str(value or '')).casefold().strip()
    if level == 1:
        value = re.sub(r'^kabupaten\b', 'kab', value)
        value = re.sub(r'^kota\s+administrasi\b', 'kota', value)
    if level == 2:
        value = re.sub(r'^(kecamatan|kec)[.\s]+', '', value)
    if level == 3:
        value = re.sub(r'^(kelurahan|kel|desa)[.\s]+', '', value)
    return re.sub(r'[^\w]+', '', value)


def city_parts(value):
    value = unicodedata.normalize('NFKC', str(value or '')).casefold().strip()
    match = re.match(r'^(kota(?:\s+administrasi)?|kabupaten|kab)(?:[.\s]+)', value)
    kind = None
    if match:
        kind = 'kota' if match[1].startswith('kota') else 'kabupaten'
        value = value[match.end():]
    return kind, normalize(value, 1)


ALIASES = json.loads(Path(__file__).with_name('regional_aliases.json').read_text())


def ranked_candidates(level, name, parent, paths):
    """Return (priority, text similarity, path, explanation), strongest first.

    Unknown parents permit exact normalized names only. Known parents restrict
    every candidate to the same full parent path. Alias/core matches remain review
    proposals, even when only one destination exists.
    """
    eligible = sorted(p for p in paths if parent is None or p[:-1] == parent)
    candidates = []
    for path in eligible:
        score = round(100 * difflib.SequenceMatcher(
            None, normalize(name, level), normalize(path[-1], level)).ratio(), 2)
        priority = 3
        reason = 'Kemiripan teks dalam induk yang sama; perlu dikonfirmasi, bukan probabilitas mapping benar.'
        if normalize(name, level) == normalize(path[-1], level):
            priority = 0
            reason = 'Nama sama setelah normalisasi; ' + ('induk belum diketahui' if parent is None else 'hierarki induk sama') + '; perlu dikonfirmasi.'
        elif parent is None:
            continue
        elif any(a['level'] == level and normalize(a['province'], 0) == normalize(path[0], 0)
                 and normalize(a['alias'], level) == normalize(name, level)
                 and a['target'] == path[-1] for a in ALIASES):
            priority = 1
            reason = 'Alias terdaftar dalam provinsi dan tingkat wilayah yang sama; perlu dikonfirmasi.'
        elif level == 1:
            source_kind, core = city_parts(name)
            target_kind, target_core = city_parts(path[-1])
            if core and core == target_core:
                priority = 2
                reason = 'Nama inti sama dalam provinsi yang sama; perbedaan awalan administratif perlu dikonfirmasi.'
                if source_kind and target_kind and source_kind != target_kind:
                    reason += ' Konflik jenis Kota/Kabupaten; jangan menetapkan ID otomatis.'
                matches = [p for p in eligible if city_parts(p[-1])[1] == core]
                if len(matches) > 1:
                    reason += ' Ambigu: lebih dari satu wilayah memiliki nama inti yang sama.'
        if priority < 3 or score >= 50:
            candidates.append((priority, score, path, reason))
    candidates.sort(key=lambda item: (item[0], -item[1], item[2]))
    # Retain all exact/alias/core evidence, plus at most three fuzzy suggestions.
    return [c for c in candidates if c[0] < 3] + [c for c in candidates if c[0] == 3][:3]
