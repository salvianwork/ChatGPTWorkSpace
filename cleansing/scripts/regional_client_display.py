"""Plain-language client presentation; matching and canonical decisions stay unchanged."""

CHOICE_FIELDS = ['Nama','Lokasi','ID_Salesforce','Status','Catatan']
CHOICE_HEADERS = [f'Pilihan_{i}_{field}' for i in range(1,4) for field in CHOICE_FIELDS]
MAPPING_HEADERS = ['Objek','Id_Sumber','Nama_Sumber','Urutan','Nama_Rekomendasi',
                   'Lokasi_Rekomendasi','ID_Salesforce_Rekomendasi','Status_Rekomendasi',
                   'Catatan_Rekomendasi','Sumber_Data','Tingkat_Ditemukan','Jumlah_Lokasi']
INFORMATIONAL_STATUSES = {'Nama ditemukan di tingkat lain',
                          'Nama sama; lokasi perlu dikonfirmasi',
                          'Nama berbeda; perlu konfirmasi'}

STATUS_TEXT = {
    'KOTA_SUMBER_PERLU_KONFIRMASI': ('Kabupaten/kota perlu dikonfirmasi','Nama kecamatan sesuai master. Pastikan perubahan kabupaten/kota pada data ini.'),
    'ID_TERVERIFIKASI': ('ID sesuai lokasi','ID ini sesuai dengan lokasi rekomendasi.'),
    'ID_ALTERNATIF_TERVERIFIKASI_UNTUK_REVIEW': ('Perlu konfirmasi ID utama','Nama dan lokasi rekomendasi sesuai master. Client perlu memastikan ID yang akan digunakan.'),
    'ID_MASTER_AMBIGU': ('Perlu pilih satu ID','Ada beberapa ID untuk lokasi ini. Client perlu memilih ID yang akan digunakan.'),
    'ID_MASTER_TIDAK_ADA_DALAM_EKSPOR': ('ID tidak ditemukan di file Salesforce','ID ini tercantum di master, tetapi tidak ditemukan di file Salesforce yang diperiksa. Pastikan ID masih digunakan.'),
    'ID_MASTER_BERBEDA_HIERARKI': ('Lokasi ID perlu diperiksa','ID pada master mengarah ke lokasi lain atau lokasinya belum dapat dipastikan. Client perlu memeriksa ID dan lokasinya.'),
    'KONFLIK_RELASI_ID_MASTER': ('Kabupaten/kota berbeda','Kabupaten/kota yang tercatat langsung berbeda dengan kabupaten/kota dari kecamatannya. Client perlu memastikan lokasi yang benar.'),
    'INDUK_ID_MASTER_PERLU_KONFIRMASI': ('Hubungan wilayah perlu dicek','Lokasi ditemukan pada master. Pastikan hubungan kecamatan, kabupaten/kota, dan provinsinya sudah benar.'),
    'ID_MASTER_PERLU_KONFIRMASI': ('ID perlu dikonfirmasi','Client perlu memastikan ID yang akan digunakan untuk lokasi ini.'),
    'RECORD_TERSEDIA_BELUM_TERVERIFIKASI': ('ID perlu diperiksa','Data untuk lokasi ini ditemukan. Client perlu memeriksa hubungan wilayah dan ID yang akan digunakan.'),
    'BELUM_ADA_ID_TERVERIFIKASI': ('ID belum dipastikan','Belum ada ID yang dapat dipastikan untuk lokasi ini. Periksa data Salesforce sebelum menentukan ID tujuan.'),
}
SOURCE_STATUS = {
    'Belum ditemukan kecocokan yang cukup aman':'Perlu konfirmasi client',
    'Lokasi cocok dengan master tetapi ID tujuan belum pasti':'Lokasi cocok; ID perlu diperiksa',
    'Informasi wilayah induk berbeda':'Wilayah yang tercatat berbeda',
    'Wilayah induk diperkirakan dari informasi lain dan perlu dikonfirmasi':'Lokasi perlu dikonfirmasi',
}


def source_text(status, note, parent, city, cross_level):
    """Keep source IDs/names intact and explain its outstanding check only once."""
    status=SOURCE_STATUS.get(status,status)
    if status=='Wilayah yang tercatat berbeda':
        note='Kabupaten/kota dari kecamatan berbeda dengan kabupaten/kota yang tercatat langsung. Client perlu memastikan lokasi yang benar.'
    elif status=='Lokasi cocok; ID perlu diperiksa':
        note='Lokasi sudah ditemukan pada master. Periksa status ID pada rekomendasi sebelum memilih ID akhir.'
    elif status=='Lokasi perlu dikonfirmasi':
        note='Lokasi ditemukan dari informasi lain. Client perlu memastikan kecamatan, kabupaten/kota, dan provinsinya.'
    elif status=='Perlu konfirmasi client':
        if not parent:
            note='Wilayah di atas data ini belum diketahui. Client perlu memastikan lokasi dan provinsinya.'
        else:
            note='Client perlu memastikan nama, lokasi, dan tingkat wilayah data ini sebelum memilih rekomendasi.'
    if cross_level:
        # Preserve every location/source bullet; replace only the closing instruction.
        marker='• Tindak Lanjut:'
        if marker in cross_level:
            cross_level=cross_level.split(marker,1)[0]+marker+'\n  Nama ditemukan pada tingkat wilayah yang berbeda. Pastikan tingkat wilayah, lokasi, dan provinsinya sebelum memilih ID akhir.'
    return status,note,cross_level


def client_candidate(d):
    """One visible ID and one concise note per recommendation.

    The status travels with the ID: displaying a tentative ID does not approve
    it for mapping. If several IDs remain, keep them together and require a choice.
    All verified/provisional IDs remain in the internal CSV for audit.
    """
    if d['Jenis_Bukti']!='KANDIDAT_OBJEK_SAMA':
        if d['Jenis_Bukti']=='NAMA_SAMA_LOKASI_LAIN':
            locations=d.get('Contoh_Lokasi','')
            count=int(d.get('Jumlah_Kemunculan') or 0)
            if count>3:locations+=f'; +{count-3} lokasi lainnya'
            return [d.get('Nama_Kandidat',''),locations,'','Nama sama; lokasi perlu dikonfirmasi',
                    'Nama ada pada master, tetapi hubungan Parent pada data sumber belum cocok atau belum lengkap. '
                    'Pastikan lokasi dan provinsi sebelum menentukan ID tujuan.']
        found=d['Jenis_Bukti']=='TEMUAN_LINTAS_TINGKAT'
        return [d.get('Nama_Kandidat',''),d.get('Contoh_Lokasi',''),'','Nama ditemukan di tingkat lain' if found else 'Nama belum ditemukan',
                'Nama ditemukan pada tingkat wilayah yang berbeda. Client perlu memastikan lokasi dan tingkat wilayahnya.' if found else 'Nama yang sama belum ditemukan pada master atau file Salesforce. Client perlu memastikan nama dan lokasinya.']
    raw_status=d['Status_Verifikasi_ID']
    status,note=STATUS_TEXT[raw_status]
    target=d.get('Id_Target_Kandidat','')
    tentative=d.get('ID_Master_Perlu_Verifikasi','')
    chosen=target or tentative
    ids=[x for x in chosen.split(';') if x]
    if len(ids)>1:
        status='Perlu pilih satu ID'
        note='Ada beberapa ID untuk lokasi ini. Client perlu memilih ID yang akan digunakan.'
    reason=d.get('Alasan','')
    context=None
    for label in ['Kelurahan','Kecamatan','Kota/Kabupaten','Provinsi']:
        prefix='Nama sumber ditemukan sebagai '+label+': '
        if reason.startswith(prefix):
            location=reason[len(prefix):].split('. Jika record',1)[0]
            parts=location.split(' | ')
            context=f'Di master, {parts[-1]} adalah {label.lower()} di {" | ".join(parts[:-1])}. '
            source_level=d.get('Tingkat_Ditemukan','').lower()
            context+=f'Jika data ini dimaksudkan sebagai {source_level}, gunakan {d["Nama_Kandidat"]}. Jika yang dimaksud {label.lower()}, tingkat wilayahnya perlu diperbaiki.'
            break
    if context:
        # The context explains the choice; add an ID warning only when still needed.
        note=context+(' '+note if not target else '')
    elif raw_status=='ID_TERVERIFIKASI':
        if 'Nama inti/alias pada master' in reason:
            note='Nama sumber sama dengan nama inti atau alias pada master dalam lokasi yang sama. Pastikan ID utama yang akan digunakan.'
        elif 'alias dalam tanda kurung' in reason:
            note='Nama inti cocok dengan master pada Parent yang sama. Nama dalam tanda kurung adalah variasi ejaan; pastikan data dan ID yang akan digunakan.'
        elif 'keterangan induk setelah koma' in reason:
            note='Nama cocok setelah keterangan wilayah setelah koma diperiksa.'
        elif 'Alias' in reason or 'alias' in reason:
            note='Nama singkat atau nama usulan mengarah ke lokasi ini. Client perlu memastikan provinsinya.'
        elif 'Nama inti' in reason:
            note='Nama cocok setelah awalan Kota/Kabupaten diperiksa.'
            if 'Konflik jenis' in reason:note+=' Pastikan apakah yang dimaksud kota atau kabupaten.'
        elif 'Kemiripan teks' in reason:
            note='Nama mirip dengan data sumber. Client perlu memastikan lokasinya.'
        elif 'Nama sama' in reason:
            note='Nama cocok dengan nama pada master.'
    if reason.startswith('Nama kecamatan sama pada master, tetapi kota/kabupaten berbeda:'):
        status='Kabupaten/kota perlu dikonfirmasi'
        note=reason
        if 'Induk/leluhur record sumber masih perlu konfirmasi.' in d.get('Alasan_Verifikasi_ID',''):
            note+=' Provinsi data sumber juga perlu dipastikan.'
        if not target and chosen and chosen!=d['Id_Sumber']:
            note+=' '+STATUS_TEXT[raw_status][1]
            if len(ids)>1:status='Perlu pilih satu ID'
        if not chosen:note+=' ID untuk lokasi ini belum dipastikan.'
    if d.get('Jenis_Rekomendasi')=='KOREKSI_RECORD_YANG_SAMA' and chosen==d['Id_Sumber']:
        note+=' ID ini sama dengan ID sumber. Perbaiki data tersebut jika lokasinya benar.'
    if d.get('Jenis_Rekomendasi')=='LOKASI_DENGAN_INDUK_SUMBER_BELUM_DIKETAHUI':
        status='Wilayah sumber perlu dikonfirmasi'
    parent_note=d.get('Petunjuk_Perbaikan_Wilayah','')
    detail=d.get('Penjelasan_ID_Client','')
    if detail:
        parent_note=parent_note.replace('Hubungan wilayah untuk lokasi rekomendasi:',
                                        'Hubungan wilayah pada data sumber untuk pilihan ini:')
        parent_note=parent_note.replace('Tidak perlu mengubah hubungan wilayah.',
                                        'Tidak perlu mengubah hubungan wilayah pada data sumber untuk pilihan ini.')
        if not chosen:
            note=context or ''
        elif chosen==d['Id_Sumber'] and d.get('Perlu_Perbaikan_Wilayah')=='YES':
            note='\n\n'.join(part for part in [context,'ID ini sama dengan ID sumber. Hubungan wilayah masih perlu diperiksa.'] if part)
            parent_note=parent_note.replace('\n• Gunakan ID sumber yang sama.','')
        note='\n\n'.join(part for part in [note,detail] if part)
    if parent_note:
        can_replace=(chosen==d['Id_Sumber'] and d.get('Perlu_Perbaikan_Wilayah')=='YES'
                     and not detail
                     and not context and raw_status in {'RECORD_TERSEDIA_BELUM_TERVERIFIKASI',
                         'INDUK_ID_MASTER_PERLU_KONFIRMASI','KOTA_SUMBER_PERLU_KONFIRMASI',
                         'KONFLIK_RELASI_ID_MASTER','ID_TERVERIFIKASI'})
        note=parent_note if can_replace else note+'\n\n'+parent_note
    if 'alias dalam tanda kurung' in reason and 'tanda kurung' not in note:
        note='Nama inti sebelum tanda kurung cocok dengan master pada Parent yang sama. Lokasi dan ID tujuan tetap perlu dikonfirmasi.\n\n'+note
    if 'Parent untuk review diambil dari relasi lama' in reason:
        context=reason.split('Parent untuk review diambil dari relasi lama',1)[1]
        note='Parent untuk review diambil dari relasi lama'+context+'\n\n'+note
    return [d['Nama_Kandidat'],d['Hierarki_Kandidat'],chosen,status,note]


NO_EXACT_WITH_CANDIDATES=('Nama persis belum ditemukan; ada kandidat',
    'Nama yang sama persis belum ditemukan. Ada kandidat nama/lokasi untuk diperiksa; kandidat belum menjadi keputusan mapping.')


def clarify_no_exact_rows(rows):
    """Qualify the no-exact-name message when the source also has candidates."""
    has_candidates={r[1] for r in rows if r[5] and r[7] not in INFORMATIONAL_STATUSES}
    result=[]
    for r in rows:
        r=list(r)
        if r[1] in has_candidates and r[7] in {'Nama belum ditemukan',NO_EXACT_WITH_CANDIDATES[0]}:
            r[7],r[8]=NO_EXACT_WITH_CANDIDATES
        result.append(r)
    return result


def mapping_row(d):
    obj={'Provinsi__c':'Provinsi','Kota_Kabupaten__c':'Kota/Kabupaten','Kecamatan__c':'Kecamatan','Kelurahan__c':'Kelurahan'}.get(d['Objek'],d['Objek'])
    return [obj,d['Id_Sumber'],d['Nama_Sumber'],d['Urutan']]+client_candidate(d)+[d['Sumber_Data'],d['Tingkat_Ditemukan'],d['Jumlah_Kemunculan']]


def ensure_selection_matches(old_options, new_options, decision, choice=''):
    """Do not silently change what an already-filled client choice points to."""
    import re
    if decision in {'Gunakan rekomendasi','Gunakan rekomendasi 1'}:decision='PILIH_KANDIDAT_1'
    match=re.fullmatch(r'PILIH_KANDIDAT_([123])',str(decision or '').strip())
    if match:
        index=int(match[1])-1
    elif not decision and str(choice or '').strip() in {'1','2','3'}:
        index=int(str(choice).strip())-1
    else:
        return
    old=tuple(v or '' for v in old_options[index])
    new=tuple(v or '' for v in new_options[index]) if index<len(new_options) else ('','','')
    if old != new:
        raise ValueError('Pilihan client yang sudah diisi akan menunjuk rekomendasi berbeda. Tinjau pilihan client tersebut sebelum merapikan rekomendasi.')
