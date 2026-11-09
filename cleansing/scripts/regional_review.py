"""Explain review candidates independently of automatic canonical mapping."""
from regional_matching import ALIASES, normalize
from regional_rename import qualified_rename_matches

REVIEW_FIELDS = {
    'Review_Kind': 'Jenis_Rekomendasi',
    'ID_Verification': 'Status_Verifikasi_ID',
    'ID_Explanation': 'Alasan_Verifikasi_ID',
    'Unverified_Master_ID': 'ID_Master_Perlu_Verifikasi',
}


def unknown_parent_city_candidates(name, proposed, paths):
    """A unique explicit alias/proposed name can be reviewed without inferring a parent."""
    found = set()
    for path in paths:
        if proposed and normalize(proposed, 1) == normalize(path[-1], 1):
            found.add(path)
        if any(a['level'] == 1 and normalize(a['alias'], 1) == normalize(name, 1)
               and a['target'] == path[-1] and a['province'] == path[0] for a in ALIASES):
            found.add(path)
    if len(found) != 1:
        return []
    return [(next(iter(found)), 'Alias/usulan nama eksplisit cocok dengan satu lokasi master. '
             'Induk dan provinsi pada record yang sedang diperiksa belum diketahui; '
             'perlu dikonfirmasi. ID final tidak ditetapkan otomatis.')]


def candidate_id_review(source, candidate_path, inventory, preferred_records, matching_records, reason='',
                        qualified_records=(),target_ids=None):
    """Return verified destination separately from IDs still requiring review.

    Inputs are read-only. A raw master ID never becomes verified simply because
    it exists. Even a safe alternative is only a candidate, not a canonical-map change.
    """
    verified = inventory['Target_Id']
    unverified = sorted(set(inventory['Master_Sheet_Id'].split(';')) - {''})
    kind = 'KANDIDAT_RECORD_TUJUAN'
    if 'Jika record dimaksudkan sebagai' in reason:
        kind = 'HIPOTESIS_TINGKAT_WILAYAH'
    if source.get('_path') == candidate_path:
        kind = 'KECOCOKAN_LOKASI_PERLU_REVIEW'
    if source['Source_Id'] in unverified or verified == source['Source_Id']:
        kind = 'KOREKSI_RECORD_YANG_SAMA'
    if source.get('_parent') is None:
        kind = 'LOKASI_DENGAN_INDUK_SUMBER_BELUM_DIKETAHUI'
    if verified:
        status = 'ID_TERVERIFIKASI'
        explanation = 'ID tujuan lolos verifikasi hierarki. Maksud record sumber tetap perlu dikonfirmasi.'
    else:
        safe = [r for r in matching_records if r.get('_path') == candidate_path and not r['_blocked'] and not r['_requires_review']
                and r['Source_Name'] == candidate_path[-1]]
        if len(safe) == 1:
            verified = safe[0]['Source_Id']
            status = 'ID_ALTERNATIF_TERVERIFIKASI_UNTUK_REVIEW'
            explanation = ('Satu record alternatif sesuai nama dan seluruh hierarki tanpa konflik/pemulihan. '
                           'ID master belum lolos; penetapan record utama tetap perlu dikonfirmasi.')
        elif unverified:
            if len(unverified) > 1:
                status = 'ID_MASTER_AMBIGU'
                explanation = 'Lebih dari satu ID pada master; belum dapat dipilih sebagai tujuan terverifikasi.'
            else:
                r = preferred_records.get(unverified[0])
                if r is None:
                    status = 'ID_MASTER_TIDAK_ADA_DALAM_EKSPOR'
                    explanation = 'ID pada master tidak ditemukan dalam ekspor sumber yang diperiksa.'
                elif r.get('_path') != candidate_path:
                    status = 'ID_MASTER_BERBEDA_HIERARKI'
                    explanation = 'ID pada master mengarah record dengan hierarki berbeda atau belum cocok.'
                elif r['_blocked']:
                    status = 'KONFLIK_RELASI_ID_MASTER'
                    explanation = 'Record ID master memiliki konflik lookup kecamatan dan kota/kabupaten; perlu dikonfirmasi.'
                elif r['_requires_review']:
                    status = 'INDUK_ID_MASTER_PERLU_KONFIRMASI'
                    explanation = 'Induk atau leluhur ID master dipulihkan dari informasi lain; verifikasi/perbaiki lookup terlebih dahulu.'
                else:
                    status = 'ID_MASTER_PERLU_KONFIRMASI'
                    explanation = 'Penetapan ID master sebagai record utama belum terverifikasi.'
        elif matching_records:
            unverified = sorted({r['Source_Id'] for r in matching_records})
            status = 'RECORD_TERSEDIA_BELUM_TERVERIFIKASI'
            explanation = 'Ada record pada lokasi ini, tetapi konflik/induk hasil pemulihan atau beberapa calon utama belum diselesaikan.'
        else:
            status = 'BELUM_ADA_ID_TERVERIFIKASI'
            explanation = 'Belum ada ID Salesforce terverifikasi untuk hierarki ini. Telusuri ekspor dan master; jangan mengambil ID dari lokasi lain.'
    if (not verified and not unverified and target_ids is not None and len(qualified_records)==1
            and qualified_records[0]['Source_Id']==source['Source_Id']
            and qualified_rename_matches(source,candidate_path,target_ids)):
        verified=source['Source_Id'];status='ID_ALTERNATIF_TERVERIFIKASI_UNTUK_REVIEW'
        kind='KOREKSI_RECORD_YANG_SAMA'
        explanation=('Nama sebelum koma sesuai master dan keterangan setelah koma cocok dengan Parent yang tercatat. '
                     'Pertahankan ID sumber sebagai usulan; cukup sesuaikan nama setelah konfirmasi. '
                     'Hubungan Parent sudah sesuai. Tidak perlu membuat data baru untuk usulan ini.')
    if (status == 'BELUM_ADA_ID_TERVERIFIKASI' and reason.startswith('Nama kecamatan sama pada master, tetapi kota/kabupaten berbeda:')
            and source.get('_parent') and source['_parent'][:1] == candidate_path[:1]
            and normalize(source['Source_Name'],2) == normalize(candidate_path[-1],2)):
        unverified = [source['Source_Id']]
        status = 'KOTA_SUMBER_PERLU_KONFIRMASI'
        kind = 'KOREKSI_RECORD_YANG_SAMA'
        explanation = 'Nama kecamatan sesuai master pada kota/kabupaten lain dalam provinsi yang sama. Konfirmasikan perubahan kota/kabupaten pada ID sumber; ID final belum dipilih.'
    if kind == 'KOREKSI_RECORD_YANG_SAMA' and verified and verified != source['Source_Id']:
        kind = 'KANDIDAT_RECORD_TUJUAN'
    if source.get('_blocked'):
        explanation += ' Record sumber juga mempunyai konflik relasi wilayah.'
    if source.get('_requires_review'):
        explanation += ' Induk/leluhur record sumber masih perlu konfirmasi.'
    if kind == 'KOREKSI_RECORD_YANG_SAMA':
        explanation += ' ID terkait sama dengan ID sumber; tinjau koreksi record ini, bukan pemindahan duplikat.'
    return {'Candidate_Target_Id': verified, 'Review_Kind': kind, 'ID_Verification': status,
            'ID_Explanation': explanation, 'Unverified_Master_ID': ';'.join(unverified)}


def unique_review_candidates(candidates):
    """One candidate per source, object and complete master path.

    IDs are resolved afterwards from this same path, so spelling/reason alone
    cannot create two copies of a destination. Keep the earliest position, but
    retain a specific location explanation instead of a generic fuzzy reason.
    Inputs and deterministic mapping records are not modified.
    """
    groups={}
    for candidate in candidates:
        groups.setdefault((candidate['Object'],candidate['Source_Id']),[]).append(candidate)
    result=[]
    for rows in groups.values():
        seen={};unique=[]
        for row in sorted(rows,key=lambda r:int(r['Rank'])):
            key=tuple(row['_path'])
            if key not in seen:
                seen[key]=len(unique);unique.append(dict(row))
            else:
                existing=unique[seen[key]]
                generic=existing['Reason'].startswith('Kemiripan teks')
                specific=(row['Reason'].startswith('Nama sumber ditemukan sebagai')
                          or row['Reason'].startswith('Exact kelurahan name within a city')
                          or row['Reason'].startswith('Matches direct city evidence'))
                if generic and specific:
                    replacement=dict(row);replacement['Rank']=existing['Rank'];unique[seen[key]]=replacement
        for rank,row in enumerate(unique,1):
            row['Rank']=rank;result.append(row)
    return result
