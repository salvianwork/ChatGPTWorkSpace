"""Compare two complete translated pipeline runs; never edits either output."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path


def read(root, filename):
    paths = list(root.rglob(filename))
    assert len(paths) == 1, (root, filename)
    with paths[0].open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def check(old, new):
    filenames = [p.name for p in old.rglob('*.csv') if p.name != 'Review_candidates.csv']
    for filename in filenames:
        assert read(old, filename) == read(new, filename), filename
    before = read(old, 'Review_candidates.csv')
    after = read(new, 'Review_candidates.csv')
    groups = defaultdict(list)
    oldgroups = defaultdict(list)
    for row in before:
        oldgroups[row['Id_Sumber']].append(row)
    for row in after:
        groups[row['Id_Sumber']].append(row)
        if row['Jenis_Bukti'] == 'TEMUAN_LINTAS_TINGKAT':
            assert not row['Id_Target_Kandidat']
    for rid, target in [('a1oJ40000009JKeIAM', 'Kota Banjar'), ('a1ofC000000PZnOQAW', 'Kota Tangerang Selatan'), ('a1pJ40000008XLbIAM', 'Tuban')]:
        assert groups[rid][0]['Nama_Kandidat'] == target
        assert groups[rid][0]['Jenis_Bukti'] == 'KANDIDAT_OBJEK_SAMA'
        print(rid, 'first recommendation:', target, groups[rid][0]['Id_Target_Kandidat'])
    kingking = groups['a1pJ40000008XLbIAM']
    assert not any(r['Nama_Kandidat'] == 'Bangilan' for r in kingking)
    assert 'Kelurahan: Jawa Timur | Kab. Tuban | Tuban | Kingking' in kingking[0]['Alasan']
    assert kingking[0]['Kemiripan'] == ''
    # Cross-level evidence remains exactly the same apart from its display rank.
    def evidence(rows):
        return sorted(tuple(sorted((k, v) for k, v in r.items() if k != 'Urutan'))
                      for r in rows if r['Jenis_Bukti'] == 'TEMUAN_LINTAS_TINGKAT')
    assert evidence(before) == evidence(after)
    def destinations(rows):
        return [(r['Nama_Kandidat'], r['Hierarki_Kandidat'], r['Id_Target_Kandidat'])
                for r in rows if r['Jenis_Bukti'] == 'KANDIDAT_OBJEK_SAMA']
    changed = sum(destinations(groups[rid]) != destinations(oldgroups[rid]) for rid in groups.keys() | oldgroups.keys())
    print('All non-candidate CSVs identical:', len(filenames))
    print('Candidate rows before/after:', len(before), len(after))
    print('Sources with changed ordered same-level recommendations:', changed)
    print('All source records, IDs, mapping decisions, updates, duplicates and cross-level evidence unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('old', type=Path)
    parser.add_argument('new', type=Path)
    args = parser.parse_args()
    check(args.old, args.new)
