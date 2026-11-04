"""Explain review candidates independently of automatic canonical mapping."""
from regional_matching import ALIASES, normalize

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


def candidate_id_review(source, candidate_path, inventory, preferred_records, matching_records, reason=''):
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
