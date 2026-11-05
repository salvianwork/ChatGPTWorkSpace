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


def name_with_validated_parent(name, level, parent):
    """Remove comma qualifiers only when each matches a known parent component.

    Qualifiers run from the immediate parent outward. Never infer a missing
    parent, discard unmatched qualifiers, or change the deterministic name key.
    """
    parts = [part.strip() for part in str(name or '').split(',')]
    if len(parts) < 2 or not all(parts) or parent is None or len(parent) != level:
        return None
    if len(parts) - 1 > len(parent):
        return None
    for offset, qualifier in enumerate(parts[1:]):
        parent_level = level - 1 - offset
        expected = parent[parent_level]
        if parent_level == 1:
            kind, core = city_parts(qualifier)
            expected_kind, expected_core = city_parts(expected)
            if not core or core != expected_core or (kind and kind != expected_kind):
                return None
        elif normalize(qualifier, parent_level) != normalize(expected, parent_level):
            return None
    return parts[0]


def ranked_candidates(level, name, parent, paths, province_paths=()):
    """Return (priority, text similarity, path, explanation), strongest first.

    Unknown parents permit exact normalized names only. Known parents restrict
    every candidate to the same full parent path. Alias/core matches remain review
    proposals, even when only one destination exists.

    A city record named exactly like a master province must not acquire unrelated
    city suggestions from text similarity. Retain exact/alias/core evidence;
    province matches remain informational cross-level findings, without IDs.
    """
    eligible = sorted(p for p in paths if parent is None or p[:-1] == parent)
    province_name = level == 1 and any(
        normalize(name, 0) == normalize(p[0], 0) for p in province_paths)
    candidates = []
    qualified_name = name_with_validated_parent(name, level, parent)
    for path in eligible:
        score = round(100 * difflib.SequenceMatcher(
            None, normalize(name, level), normalize(path[-1], level)).ratio(), 2)
        priority = 3
        reason = 'Kemiripan teks dalam induk yang sama; perlu dikonfirmasi, bukan probabilitas mapping benar.'
        if normalize(name, level) == normalize(path[-1], level):
            priority = 0
            reason = 'Nama sama setelah normalisasi; ' + ('induk belum diketahui' if parent is None else 'hierarki induk sama') + '; perlu dikonfirmasi.'
        elif qualified_name is not None and normalize(qualified_name, level) == normalize(path[-1], level):
            priority = 0
            reason = ('Nama wilayah sama setelah keterangan induk setelah koma dicocokkan '
                      'dengan hierarki induk yang sudah teridentifikasi; perlu dikonfirmasi. '
                      'Nama sumber dipertahankan dan ID final tidak ditetapkan otomatis.')
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
        if province_name and priority == 3:
            continue
        if priority < 3 or score >= 50:
            candidates.append((priority, score, path, reason))
    candidates.sort(key=lambda item: (item[0], -item[1], item[2]))
    # Retain all exact/alias/core evidence, plus at most three fuzzy suggestions.
    return [c for c in candidates if c[0] < 3] + [c for c in candidates if c[0] == 3][:3]


def district_context_candidates(name, parent, kelurahan_paths):
    """Suggest a district from an exact child name in the resolved city.

    This is a hypothesis about the intended district, not a match to the source
    record's level. Keep every matching district when the hierarchy is ambiguous.
    """
    if parent is None:
        return []
    found = {}
    for path in sorted(kelurahan_paths):
        if path[:2] != parent or normalize(path[-1], 3) not in {normalize(name, 3), normalize(str(name) + ' Kota', 3)}:
            continue
        district = path[:3]
        reason = (
            'Nama sumber ditemukan sebagai Kelurahan: ' + ' | '.join(path) + '. '
            'Jika record dimaksudkan sebagai Kecamatan, rekomendasi berdasarkan '
            'induk kelurahan adalah ' + path[2] + '. Jika record dimaksudkan sebagai '
            'Kelurahan, konfirmasikan koreksi tingkat wilayah dan lokasinya. '
            'ID tujuan final tidak ditetapkan otomatis; perlu dikonfirmasi.'
        )
        if normalize(path[-1], 3) != normalize(name, 3):
            reason += ' Variasi nama anak dengan akhiran Kota; bukan kecocokan nama persis.'
        found.setdefault(district, reason)
    if len(found) > 1:
        found = {p: reason + ' Ambigu: terdapat lebih dari satu kecamatan induk dalam kota/kabupaten ini.'
                 for p, reason in found.items()}
    return list(found.items())


def city_context_candidates(name, parent, district_paths, kelurahan_paths=()):
    """Suggest cities from exact lower-level names.

    Restrict known provinces. With unknown province, allow only one distinct
    city across all exact master hits, with explicit confirmation still needed.
    Source relationships and automatic mapping are never changed.
    """
    found = {}
    for level, paths, label in [(2, district_paths, 'Kecamatan'), (3, kelurahan_paths, 'Kelurahan')]:
        for path in sorted(paths):
            if (parent is not None and path[:1] != parent) or normalize(path[-1], level) != normalize(name, level):
                continue
            city = path[:2]
            reason = (
                'Nama sumber ditemukan sebagai ' + label + ': ' + ' | '.join(path) + '. '
                'Jika record dimaksudkan sebagai Kota/Kabupaten, rekomendasi berdasarkan '
                'hierarki master adalah ' + path[1] + '. Jika record sebenarnya dimaksudkan sebagai '
                + label + ', konfirmasikan koreksi tingkat wilayah dan lokasinya. '
                'ID tujuan final tidak ditetapkan otomatis; perlu dikonfirmasi.'
            )
            found.setdefault(city, reason)
    if parent is None and len(found) != 1:
        return []
    if parent is None:
        found = {p: reason + ' Provinsi pada data sumber belum diketahui dan perlu dikonfirmasi.' for p,reason in found.items()}
    if len(found) > 1:
        found = {p: reason + ' Ambigu: terdapat lebih dari satu kota/kabupaten dalam provinsi ini.'
                 for p, reason in found.items()}
    return list(found.items())


def district_other_city_candidates(name, parent, district_paths):
    """Exact district name in another city of the same known province, review only."""
    if parent is None or len(parent) != 2:
        return []
    hits=sorted({p for p in district_paths if normalize(p[-1],2)==normalize(name,2)})
    if any(p[:-1]==parent for p in hits):
        return []
    matches=[p for p in hits if p[:1]==parent[:1] and p[:-1]!=parent]
    result=[]
    for path in matches:
        reason=('Nama kecamatan sama pada master, tetapi kota/kabupaten berbeda: '
                + ' | '.join(path) + '. Kabupaten/kota pada data sumber adalah '
                + parent[-1] + '. Client perlu memastikan perubahan kabupaten/kota.')
        if len(matches)>1:reason+=' Nama ini ada di beberapa kabupaten/kota pada provinsi yang sama. Pilih lokasi yang benar.'
        result.append((path,reason))
    return result
