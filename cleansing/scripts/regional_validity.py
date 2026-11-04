"""Separate correct region data from the unresolved choice of canonical ID."""
REGION_FIELDS = {
    'Region_Validation': 'Status_Validasi_Wilayah',
    'Primary_ID_Decision': 'Status_Penetapan_ID_Utama',
}
PENDING_REGION = 'VALID_WILAYAH_MENUNGGU_ID_UTAMA'
PENDING_PRIMARY = 'MENUNGGU_KONFIRMASI_CLIENT'
VALID_SHEETS = ['VALID PROVINSI','VALID KOTA','VALID KECAMATAN','VALID KELURAHAN']
OBJECT_LABELS = {'Provinsi__c':'Provinsi','Kota_Kabupaten__c':'Kota/Kabupaten','Kecamatan__c':'Kecamatan','Kelurahan__c':'Kelurahan'}


def valid_region_pending_primary(source, target_ids):
    """Require exact name and existing verified parent IDs, with no repair needed.

    This never selects a canonical ID or overrides source Status/Action. Rows
    needing a name correction, recovered relationship or direct-city repair stay
    in manual review, even when their intended location has already been found.
    """
    path=source.get('_path')
    if (not path or source.get('Status')!='MAPPED_TARGET_UNRESOLVED'
            or source.get('Match_Method')!='EXACT_HIERARCHY'
            or source['Source_Name']!=path[-1] or source['_blocked'] or source['_requires_review']):
        return False
    level=len(path)-1
    if level:
        parent=target_ids[level-1].get(path[:-1],'')
        if not parent or source['Source_Parent_Id']!=parent:
            return False
    if level==3:
        city=target_ids[1].get(path[:2],'')
        if not city or source['Source_Direct_City_Id']!=city:
            return False
    return True


def translated_path(row):
    return tuple(row[k] for k in ['Provinsi_Target','KotaKabupaten_Target','Kecamatan_Target','Kelurahan_Target'] if row[k])


def valid_client_row(row):
    """Existing valid-sheet columns, with explicit pending-primary wording."""
    path=translated_path(row)
    note='Valid wilayah. Penetapan ID utama masih menunggu konfirmasi client.'
    if row.get('Catatan'):
        note+=' Nama wilayah pada tampilan file sumber perlu dicocokkan kembali; ID hubungan wilayah sudah sesuai.'
    return [OBJECT_LABELS[row['Objek']],row['Id_Sumber'],row['Nama_Sumber'],path[-1],' | '.join(path),
            row['Id_Induk_Sumber'] or None,row['Nama_Induk_Dalam_Ekspor'] or None,row['Id_Induk_Target'] or None,
            'Nama dan hubungan wilayah sudah sesuai dengan master.',
            'Data wilayah sudah sesuai. Penetapan ID utama masih menunggu konfirmasi client.',
            'Pertahankan data ini. Konfirmasikan ID utama dan tulis keputusan pada Catatan_Pemeriksaan.',note]
