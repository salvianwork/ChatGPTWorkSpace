"""Compare two complete translated pipeline runs; never edits either output."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_matching import normalize


def read(root, filename):
    paths = list(root.rglob(filename))
    assert len(paths) == 1, (root, filename)
    with paths[0].open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def check(old, new):
    filenames = [p.name for p in old.rglob('*.csv') if p.name != 'Review_candidates.csv']
    for filename in filenames:
        previous,current=read(old,filename),read(new,filename)
        assert len(previous)==len(current),filename
        for a,b in zip(previous,current,strict=True):
            assert all(b[k]==v for k,v in a.items()),filename
            assert set(b)-set(a) <= {'Status_Validasi_Wilayah','Status_Penetapan_ID_Utama'},filename
    before = read(old, 'Review_candidates.csv')
    after = read(new, 'Review_candidates.csv')
    provinces={normalize(r['Hierarki_Master'],0) for r in read(old,'Master_target_inventory.csv')
               if r['Objek']=='Provinsi__c'}
    def province_fuzzy(row):
        return (row['Objek']=='Kota_Kabupaten__c' and normalize(row['Nama_Sumber'],0) in provinces
                and row['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA' and row['Alasan'].startswith('Kemiripan teks'))
    removed=[row for row in before if province_fuzzy(row)]
    expected=[row for row in before if not province_fuzzy(row)]
    if removed:
        without_rank=lambda row:{k:v for k,v in row.items() if k!='Urutan'}
        assert list(map(without_rank,after))==list(map(without_rank,expected)), 'Unexpected candidate change'
        lampung=[r for r in after if r['Id_Sumber']=='a1oJ40000009gGfIAI']
        assert lampung and all(r['Jenis_Bukti']=='TEMUAN_LINTAS_TINGKAT' for r in lampung)
        assert {r['Sumber_Data'] for r in lampung}=={'Master','Ekspor Salesforce'}
        assert all(r['Tingkat_Ditemukan']=='Provinsi' and not r['Id_Target_Kandidat'] for r in lampung)
    if before and 'Petunjuk_Perbaikan_Wilayah' not in before[0] and 'Petunjuk_Perbaikan_Wilayah' in after[0]:
        for previous,current in zip(before,after,strict=True):
            assert all(current[k]==v for k,v in previous.items()),previous['Id_Sumber']
        print('Parent instructions only: all existing candidate CSV fields unchanged.')
    groups = defaultdict(list)
    oldgroups = defaultdict(list)
    expectedgroups = defaultdict(list)
    for row in before:
        oldgroups[row['Id_Sumber']].append(row)
    for row in expected:
        expectedgroups[row['Id_Sumber']].append(row)
    for row in after:
        groups[row['Id_Sumber']].append(row)
        if row['Jenis_Bukti'] == 'TEMUAN_LINTAS_TINGKAT':
            assert not row['Id_Target_Kandidat']
    for rid, target in [('a1oJ40000009JKeIAM', 'Kota Banjar'), ('a1ofC000000PZnOQAW', 'Kota Tangerang Selatan'), ('a1pJ40000008XLbIAM', 'Tuban'), ('a1ofC0000003GwHQAU', 'Kab. Bekasi'), ('a1pJ40000008X3UIAU', 'Buay Pemaca')]:
        assert groups[rid][0]['Nama_Kandidat'] == target
        assert groups[rid][0]['Jenis_Bukti'] == 'KANDIDAT_OBJEK_SAMA'
        print(rid, 'first recommendation:', target, groups[rid][0]['Id_Target_Kandidat'])
    kingking = groups['a1pJ40000008XLbIAM']
    assert not any(r['Nama_Kandidat'] == 'Bangilan' for r in kingking)
    assert 'Kelurahan: Jawa Timur | Kab. Tuban | Tuban | Kingking' in kingking[0]['Alasan']
    assert kingking[0]['Kemiripan'] == ''
    babelan = groups['a1ofC0000003GwHQAU']
    assert not any(r['Nama_Kandidat'] == 'Kab. Sumedang' for r in babelan)
    assert 'Kecamatan: Jawa Barat | Kab. Bekasi | Babelan' in babelan[0]['Alasan']
    assert babelan[0]['Kemiripan'] == ''
    pemaca = groups['a1pJ40000008X3UIAU'][0]
    assert pemaca['Hierarki_Kandidat'] == 'Sumatra Selatan | Kab. Ogan Komering Ulu Selatan | Buay Pemaca'
    assert 'keterangan induk setelah koma' in pemaca['Alasan']
    for rid, name in [('a1ofC000001vBcaQAE','Kota Jakarta Barat'),('a1pJ40000008X4aIAE','Dusun Selatan'),('a1pJ40000008XVWIA2','Martapura'),('a1nfC00000VF9PmQAL','Lohong')]:
        candidate=groups[rid][0]
        assert candidate['Nama_Kandidat']==name,(rid,candidate)
        assert candidate['Status_Verifikasi_ID'] and candidate['Alasan_Verifikasi_ID']
    assert groups['a1ofC000001vBcaQAE'][0]['Id_Target_Kandidat']=='a1oJ40000009JLZIA2'
    assert groups['a1pJ40000008X4aIAE'][0]['Id_Target_Kandidat']=='a1pfC00000DcGqWQAV'
    huta=groups['a1pJ40000008XDhIAM']
    huta_choices=[r for r in huta if r['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA']
    assert {r['Nama_Kandidat'] for r in huta_choices}=={'Muara','Purbatua'}
    muara=next(r for r in huta_choices if r['Nama_Kandidat']=='Muara')
    assert not muara['Id_Target_Kandidat'] and muara['Status_Verifikasi_ID']=='BELUM_ADA_ID_TERVERIFIKASI'
    for rid,status in [('a1nJ4000000KUKFIA4','KONFLIK_RELASI_ID_MASTER'),('a1nfC00000VF9PmQAL','INDUK_ID_MASTER_PERLU_KONFIRMASI'),('a1pJ40000008XVWIA2','INDUK_ID_MASTER_PERLU_KONFIRMASI')]:
        candidate=groups[rid][0]
        assert not candidate['Id_Target_Kandidat']
        assert candidate['Status_Verifikasi_ID']==status
        assert candidate['ID_Master_Perlu_Verifikasi']==rid
        assert candidate['Jenis_Rekomendasi']=='KOREKSI_RECORD_YANG_SAMA'
    for rows in groups.values():
        for candidate in rows:
            if candidate['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA':
                assert candidate['Status_Verifikasi_ID'] and candidate['Alasan_Verifikasi_ID']
                if candidate['Id_Target_Kandidat']:
                    assert candidate['Status_Verifikasi_ID'] in {'ID_TERVERIFIKASI','ID_ALTERNATIF_TERVERIFIKASI_UNTUK_REVIEW'}
    timur=groups['a1ofC0000004iFaQAI'][0]
    assert timur['Nama_Kandidat']=='Kota Bogor' and timur['Hierarki_Kandidat']=='Jawa Barat | Kota Bogor'
    assert timur['Id_Target_Kandidat']=='a1oJ40000009JOfIAM'
    assert 'Kecamatan: Jawa Barat | Kota Bogor | Bogor Timur' in timur['Alasan']
    barat=groups['a1pJ40000008X21IAE'][0]
    assert barat['Nama_Kandidat']=='Bogor Barat' and barat['Hierarki_Kandidat']=='Jawa Barat | Kota Bogor | Bogor Barat'
    assert not barat['Id_Target_Kandidat'] and barat['ID_Master_Perlu_Verifikasi']=='a1pJ40000008X21IAE'
    assert barat['Status_Verifikasi_ID']=='KOTA_SUMBER_PERLU_KONFIRMASI'
    assert barat['Jenis_Rekomendasi']=='KOREKSI_RECORD_YANG_SAMA'
    legok=groups['a1nJ4000000Kc2yIAC'][0]
    assert legok['Nama_Kandidat']=='Legok Kidul'
    assert 'Lengkapi kecamatan dengan Paseh, ID a1pJ40000008XggIAE.' in legok['Petunjuk_Perbaikan_Wilayah']
    assert 'Kabupaten Sumedang sudah sesuai.' in legok['Petunjuk_Perbaikan_Wilayah']
    assert 'Gunakan ID sumber yang sama.' in legok['Petunjuk_Perbaikan_Wilayah']
    assert legok['Perlu_Perbaikan_Wilayah']=='YES'
    # Cross-level evidence remains exactly the same apart from its display rank.
    def evidence(rows):
        return sorted(tuple(sorted((k, v) for k, v in r.items() if k not in {'Urutan','Jenis_Rekomendasi','Status_Verifikasi_ID','Alasan_Verifikasi_ID','ID_Master_Perlu_Verifikasi','Petunjuk_Perbaikan_Wilayah','Perlu_Perbaikan_Wilayah'}))
                      for r in rows if r['Jenis_Bukti'] == 'TEMUAN_LINTAS_TINGKAT')
    assert evidence(before) == evidence(after)
    def destinations(rows):
        return [(r['Nama_Kandidat'], r['Hierarki_Kandidat'], r['Id_Target_Kandidat'])
                for r in rows if r['Jenis_Bukti'] == 'KANDIDAT_OBJEK_SAMA']
    # Only explicitly suppressed province-name fuzzy suggestions may disappear.
    # Distinct remaining locations and all verified IDs must remain unchanged.
    for rid in groups.keys() | oldgroups.keys():
        assert destinations(groups[rid])==list(dict.fromkeys(destinations(expectedgroups[rid]))),rid
        def visible_ids(rows):
            return [(r['Nama_Kandidat'],r['Hierarki_Kandidat'],r['Id_Target_Kandidat'] or r.get('ID_Master_Perlu_Verifikasi',''))
                    for r in rows if r['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA']
        assert visible_ids(groups[rid])==list(dict.fromkeys(visible_ids(expectedgroups[rid]))),rid
        target_rows=[r for r in groups[rid] if r['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA']
        paths=[r['Hierarki_Kandidat'] for r in target_rows]
        assert len(paths)==len(set(paths)),rid
    bekasi=[r for r in groups['a1ofC000002XjI9QAK'] if r['Jenis_Bukti']=='KANDIDAT_OBJEK_SAMA']
    assert len(bekasi)==1 and bekasi[0]['Nama_Kandidat']=='Kab. Bekasi'
    changed = sum(destinations(groups[rid]) != destinations(oldgroups[rid]) for rid in groups.keys() | oldgroups.keys())
    print('All prior fields in non-candidate CSVs unchanged:',len(filenames))
    print('Candidate rows before/after:', len(before), len(after))
    print('Sources with changed ordered same-level recommendations:', changed)
    print('Province-name fuzzy candidates removed:',len(removed))
    print('All source records, IDs, mapping decisions, updates, duplicates and cross-level evidence unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('old', type=Path)
    parser.add_argument('new', type=Path)
    args = parser.parse_args()
    check(args.old, args.new)
