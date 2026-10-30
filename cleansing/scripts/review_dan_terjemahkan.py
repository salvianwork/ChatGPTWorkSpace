from pathlib import Path
import argparse,csv,collections,re,unicodedata,json,hashlib
import pandas as pd
import openpyxl
parser=argparse.ArgumentParser(description='Telusuri nama lintas tingkat dan terjemahkan paket cleansing ke Bahasa Indonesia. Tidak mengubah Salesforce.')
parser.add_argument('--input-dir',type=Path,required=True)
parser.add_argument('--output-dir',type=Path,required=True,help='Folder output berisi CSV hasil generator dalam subfolder penggunaan')
a=parser.parse_args();ROOT=a.input_dir;OUT=a.output_dir
LEVELS=['Provinsi','Kota/Kabupaten','Kecamatan','Kelurahan'];PREFIX=['Provinsi','KotaKabupaten','Kecamatan','Kelurahan'];OBJECTS=['Provinsi__c','Kota_Kabupaten__c','Kecamatan__c','Kelurahan__c']
H={
'Object':'Objek','Source_Id':'Id_Sumber','Source_Name':'Nama_Sumber','Source_Parent_Id':'Id_Induk_Sumber','Source_Direct_City_Id':'Id_Kota_Langsung_Sumber','Source_Direct_City_Resolved_Path':'Hierarki_Kota_Langsung_Terurai','Source_Legacy_Kecamatans':'Kecamatan_Lama_Sumber','Source_Postal_Code':'Kode_Pos_Sumber','Supplied_Name_Changes':'Usulan_Perubahan_Nama_Sumber','Resolved_Parent_Path':'Hierarki_Induk_Terurai','Source_Parent_Display':'Nama_Induk_Dalam_Ekspor','Gap_Analysis_Unmatched':'Tidak_Cocok_Dalam_Analisis_Gap','Match_Method':'Metode_Pencocokan','Parent_Evidence':'Bukti_Induk','Target_Id':'Id_Target','Target_Name':'Nama_Target','Target_Provinsi':'Provinsi_Target','Target_KotaKabupaten':'KotaKabupaten_Target','Target_Kecamatan':'Kecamatan_Target','Target_Kelurahan':'Kelurahan_Target','Target_Parent_Id':'Id_Induk_Target','Status':'Status','Action':'Tindakan','Notes':'Catatan','Rank':'Urutan','Similarity':'Kemiripan','Candidate_Path':'Hierarki_Kandidat','Candidate_Name':'Nama_Kandidat','Reason':'Alasan','Candidate_Target_Id':'Id_Target_Kandidat','Kelurahan_Master_Path':'Hierarki_Kelurahan_Master','Candidate_Kecamatan_Path':'Hierarki_Kecamatan_Kandidat','Candidate_Kecamatan_Target_Id':'Id_Kecamatan_Target_Kandidat','Master_Path':'Hierarki_Master','Master_Count':'Jumlah_Master','Salesforce_Count':'Jumlah_Salesforce','Gap_Analysis_Unmatched':'Tidak_Cocok_Dalam_Analisis_Gap','Gap_Invalid_Count':'Jumlah_Tidak_Valid_Dalam_Gap','Original_Name':'Nama_Sebelumnya','Original_Parent_Id':'Id_Induk_Sebelumnya','Original_Direct_City_Id':'Id_Kota_Langsung_Sebelumnya','Deterministic_Source_Count':'Jumlah_Sumber_Cocok_Deterministik','Master_Sheet_Id':'Id_Dalam_Sheet_Master','Target_Resolution':'Hasil_Verifikasi_Target','Parent_Target_Id':'Id_Target_Induk','Provisioning_Action':'Tindakan_Penyediaan_Target','Key':'Kunci','Issue':'Masalah','Rows':'Jumlah_Baris','Postal_Codes':'Kode_Pos','Workbook_Master_Count':'Jumlah_Master_Workbook','Full_Hierarchy_Master_Count':'Jumlah_Master_Hierarki_Lengkap','Workbook_SF_Count':'Jumlah_Salesforce_Workbook','CSV_SF_Count':'Jumlah_Salesforce_CSV','Workbook_Unmatched':'Tidak_Cocok_Workbook','CSV_Legacy_Unmatched':'Tidak_Cocok_CSV_Kunci_Lama','CSV_Full_Key_Unmatched':'Tidak_Cocok_CSV_Kunci_Lengkap','File':'Berkas','Bytes':'Ukuran_Byte','SHA256':'SHA256','Evidence_Type':'Jenis_Bukti','Found_Level':'Tingkat_Ditemukan','Data_Source':'Sumber_Data','Found_Count':'Jumlah_Kemunculan','Location_Examples':'Contoh_Lokasi','Parent_Context':'Konteks_Induk'}
V={
'VALID_CANONICAL':'VALID_RECORD_UTAMA','CANONICAL_UPDATE_PROPOSED':'USULAN_UPDATE_RECORD_UTAMA','MAPPED_DUPLICATE':'DUPLIKAT_DIPETAKAN','MAPPED_TARGET_UNRESOLVED':'COCOK_MASTER_ID_TARGET_BELUM_TERVERIFIKASI','MAPPED_PARENT_TARGET_UNRESOLVED':'ID_TARGET_INDUK_BELUM_TERVERIFIKASI','REVIEW_RECOVERED_PARENT':'TINJAU_INDUK_HASIL_PEMULIHAN','REVIEW_PARENT_CONFLICT':'TINJAU_KONFLIK_INDUK','REVIEW_UNMATCHED':'TINJAU_BELUM_COCOK',
'KEEP':'PERTAHANKAN','UPDATE_AFTER_REVIEW':'UPDATE_SETELAH_DITINJAU','REPOINT_REFERENCES_THEN_RETIRE_AFTER_REVIEW':'PINDAHKAN_REFERENSI_LALU_NONAKTIFKAN_SETELAH_DITINJAU','RESOLVE_OR_CREATE_CANONICAL_TARGET':'VERIFIKASI_ATAU_BUAT_RECORD_TARGET_UTAMA','RESOLVE_PARENT_TARGET':'VERIFIKASI_TARGET_INDUK','REVIEW_ONLY':'HANYA_UNTUK_DITINJAU','REVIEW_RELATIONSHIP_RECOVERY':'TINJAU_PEMULIHAN_RELASI',
'EXACT_HIERARCHY':'COCOK_PERSIS_DALAM_HIERARKI','NORMALIZED_HIERARCHY':'COCOK_SETELAH_NORMALISASI_DALAM_HIERARKI','NO_MATCH_IN_PARENT':'TIDAK_COCOK_DALAM_INDUK','PARENT_UNRESOLVED':'INDUK_BELUM_TERVERIFIKASI','AMBIGUOUS_NORMALIZATION':'HASIL_NORMALISASI_AMBIGU','USER_SUPPLIED_CITY_NAME_CHANGE':'USULAN_NAMA_KOTA_DARI_PENGGUNA',
'PARENT_LOOKUP_ID':'ID_LOOKUP_INDUK','PROVINCE_TEXT_RECOVERY':'PEMULIHAN_DARI_NAMA_PROVINSI','UNIQUE_CITY_TEXT_RECOVERY':'PEMULIHAN_DARI_NAMA_KOTA_UNIK','CITY_AND_DISTRICT_TEXT_RECOVERY':'PEMULIHAN_DARI_KOTA_DAN_NAMA_KECAMATAN','LEGACY_KECAMATAN_ID_RECOVERY':'PEMULIHAN_DARI_ID_KECAMATAN_LAMA',
'VERIFIED_MASTER_ID':'ID_MASTER_TERVERIFIKASI','UNIQUE_EXISTING_CANONICAL_NAME':'RECORD_UNIK_DENGAN_NAMA_MASTER','UNIQUE_DETERMINISTIC_SOURCE_REQUIRES_RENAME':'SUMBER_COCOK_UNIK_PERLU_PERUBAHAN_NAMA','NO_CANONICAL_RECORD':'BELUM_ADA_RECORD_UTAMA_TERVERIFIKASI','REVIEW_MASTER_ID_CONFLICT':'TINJAU_KONFLIK_ID_MASTER','REVIEW_MULTIPLE_CANONICAL_RECORDS':'TINJAU_BEBERAPA_CALON_RECORD_UTAMA','EXISTS':'SUDAH_ADA','INSERT_AFTER_PARENT_EXISTS':'USULAN_INSERT_SETELAH_INDUK_TERSEDIA','REVIEW_TARGET_ID':'TINJAU_ID_TARGET',
'MASTER_TARGET_ID_DOES_NOT_VERIFY_AGAINST_FULL_HIERARCHY':'ID_TARGET_MASTER_BELUM_LOLOS_VERIFIKASI_HIERARKI_LENGKAP','MASTER_SHEET_KEY_NOT_UNIQUE_OR_NOT_IN_SERVICE_TERRITORY':'KUNCI_SHEET_MASTER_TIDAK_UNIK_ATAU_TIDAK_ADA_DALAM_MASTER_WILAYAH',
'Same linked or recovered parent':'Induk yang sama berdasarkan lookup atau hasil pemulihan; kandidat masih perlu ditinjau.',
'Exact normalized name; parent unresolved':'Nama sama setelah normalisasi, tetapi induk belum terverifikasi.',
'Matches direct city evidence; conflicts with linked district':'Cocok dengan bukti kota langsung, tetapi bertentangan dengan kecamatan pada lookup.',
'Exact kelurahan name within a city supported by source evidence; confirm district and conflicting city links':'Nama kelurahan sama dalam kota yang didukung bukti sumber; konfirmasikan kecamatan dan konflik relasi kota.',
'Source district name matches a master kelurahan in this city; confirm intended district':'Nama kecamatan sumber ditemukan sebagai kelurahan dalam master kota ini; verifikasi tingkat wilayah yang dimaksud.',
'Review dependencies; repoint references; retire duplicate only after validation':'Tinjau seluruh referensi; pindahkan referensi; nonaktifkan duplikat hanya setelah verifikasi.',
'Direct city lookup disagrees with city of linked kecamatan':'Lookup kota langsung berbeda dari kota milik kecamatan pada lookup',
'Exported parent display differs from lookup record name':'Nama induk dalam ekspor berbeda dari nama record pada lookup',
'Parent lookup missing or unresolved; province text used':'Lookup induk kosong atau belum terverifikasi; menggunakan nama provinsi',
'Parent lookup missing or unresolved; unique city text used':'Lookup induk kosong atau belum terverifikasi; menggunakan nama kota yang unik',
'Recovered parent from city lookup and district text':'Induk dipulihkan dari lookup kota dan nama kecamatan',
'Recovered parent from legacy Kecamatans__c ID':'Induk dipulihkan dari ID lama pada Kecamatans__c',
'Recovered kecamatan conflicts with direct city lookup':'Kecamatan hasil pemulihan bertentangan dengan lookup kota langsung',
'Used supplied Name Changes column, validated within province':'Menggunakan kolom Name Changes dari pengguna, telah dicocokkan dalam provinsi yang sama',
'Yes':'Ya','No':'Tidak'}
H.update({k:v for k,v in V.items() if k in ['VALID_CANONICAL','CANONICAL_UPDATE_PROPOSED','MAPPED_DUPLICATE','MAPPED_TARGET_UNRESOLVED','MAPPED_PARENT_TARGET_UNRESOLVED','REVIEW_RECOVERED_PARENT','REVIEW_PARENT_CONFLICT','REVIEW_UNMATCHED']})
files={p.name:p for p in OUT.rglob('*.csv')};assert len(files)==27,'Jalankan pada keluaran generator asli (27 CSV).'
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f);return reader.fieldnames,list(reader)
tables={name:read(p) for name,p in files.items()}
allrows=[tables[p+'_all_records.csv'][1] for p in PREFIX]
assert 'Source_Id' in tables['KotaKabupaten_all_records.csv'][0], 'Paket sudah diterjemahkan. Regenerasikan keluaran asli sebelum mengulang.'
byid=[{x['Source_Id']:x for x in rows} for rows in allrows]
def norm(name,level):
 x=unicodedata.normalize('NFKC',str(name or '')).casefold().strip()
 if level==1:
  x=re.sub(r'^kabupaten\b','kab',x);x=re.sub(r'^kota\s+administrasi\b','kota',x)
 if level==2:x=re.sub(r'^(kecamatan|kec)[.\s]+','',x)
 if level==3:x=re.sub(r'^(kelurahan|kel|desa)[.\s]+','',x)
 return re.sub(r'[^\w]+','',x)
wb=openpyxl.load_workbook(ROOT/'Service Territory MASTER FIX.xlsx',read_only=True,data_only=True)
paths=set()
for row in wb['Service Territory'].iter_rows(min_row=2,values_only=True):
 if row[0] and row[1] and row[3] and row[5]:paths.add((row[0],row[1],row[3],row[5]))
wb.close();indices=[];sf=[]
for lev in range(4):
 ix=collections.defaultdict(set);sx=collections.defaultdict(set)
 for p in paths:ix[norm(p[lev],lev)].add(p[:lev+1])
 for x in allrows[lev]:
  parent=tuple(x.get('Resolved_Parent_Path','').split(' | ')) if x.get('Resolved_Parent_Path') else ()
  sx[norm(x['Source_Name'],lev)].add(parent+(x['Source_Name'],))
 indices.append(ix);sf.append(sx)
old=tables['Review_candidates.csv'][1];candidates=[];removed=0
for x in old:
 if x['Reason'].startswith('Source district name matches a master kelurahan'):
  removed+=1;continue
 x=dict(x);x.update(Evidence_Type='KANDIDAT_OBJEK_SAMA',Found_Level=LEVELS[OBJECTS.index(x['Object'])],Data_Source='Master',Found_Count='',Location_Examples='',Parent_Context='')
 candidates.append(x)
cross=[];unmatched=[];nohit=[]
for lev,rows in enumerate(allrows):
 for x in rows:
  if x['Match_Method'] in ('EXACT_HIERARCHY','NORMALIZED_HIERARCHY','USER_SUPPLIED_CITY_NAME_CHANGE'):continue
  unmatched.append((lev,x));found=False
  for dest in range(4):
   if dest==lev:continue
   key=norm(x['Source_Name'],dest)
   for origin,index in [('Master',indices[dest]),('Ekspor Salesforce',sf[dest])]:
    hits=sorted(index.get(key,set()))
    if not hits:continue
    found=True
    sameprovince=[p for p in hits if x.get('Resolved_Parent_Path') and p[0]==x['Resolved_Parent_Path'].split(' | ')[0]]
    context='Ada kemunculan dalam provinsi asal.' if sameprovince else 'Tidak ada kemunculan yang terverifikasi dalam provinsi asal, atau provinsi asal belum diketahui.'
    examples=sorted(hits,key=lambda p:(p not in sameprovince,p))[:5]
    reason=f'Nama "{x["Source_Name"]}" ditemukan pada {LEVELS[dest].lower()} di {origin.lower()}. Ini temuan pada tingkat wilayah lain, bukan pemetaan lokasi yang sudah benar. ID kandidat sengaja dikosongkan. '
    if origin=='Ekspor Salesforce':reason+='Kemunculan dalam ekspor belum membuktikan bahwa data tersebut valid. '
    reason+=context
    cr={'Object':OBJECTS[lev],'Source_Id':x['Source_Id'],'Source_Name':x['Source_Name'],'Rank':'','Similarity':'','Candidate_Path':'','Candidate_Name':x['Source_Name'],'Reason':reason,'Candidate_Target_Id':'','Evidence_Type':'TEMUAN_LINTAS_TINGKAT','Found_Level':LEVELS[dest],'Data_Source':origin,'Found_Count':str(len(hits)),'Location_Examples':'; '.join(' | '.join(p) for p in examples),'Parent_Context':context}
    cross.append(cr)
  if not found and not any(norm(x['Source_Name'],lev) in indices[lev] for _ in [0]):
   # No exact normalized master name at any level; do not imply fuzzy candidates are confirmed matches.
   cr={'Object':OBJECTS[lev],'Source_Id':x['Source_Id'],'Source_Name':x['Source_Name'],'Rank':'','Similarity':'','Candidate_Path':'','Candidate_Name':'','Reason':'Tidak ditemukan nama yang sama setelah normalisasi pada tingkat lain dalam master atau ekspor Salesforce. Kandidat berbasis kemiripan, bila ada, tetap perlu ditinjau.','Candidate_Target_Id':'','Evidence_Type':'BELUM_DITEMUKAN','Found_Level':'','Data_Source':'Master dan ekspor Salesforce','Found_Count':'0','Location_Examples':'','Parent_Context':''}
   nohit.append(cr)
# Put cross-level findings before the older same-object fuzzy suggestions for each source.
order={x['Source_Id']:(lev,j) for lev,rows in enumerate(allrows) for j,x in enumerate(rows)}
cross_ids={x['Source_Id'] for x in cross}
suppress={x['Source_Id'] for lev,x in unmatched if x['Source_Id'] in cross_ids and norm(x['Source_Name'],lev) not in indices[lev]}
suppressed=sum(x['Source_Id'] in suppress for x in candidates)
candidates=[x for x in candidates if x['Source_Id'] not in suppress]
candidates=cross+nohit+candidates
seen=set();dedup=[]
for x in candidates:
 key=(x['Object'],x['Source_Id'],x['Evidence_Type'],x['Candidate_Path'],x['Found_Level'],x['Data_Source'],x['Reason'])
 if key not in seen:seen.add(key);dedup.append(x)
candidates=sorted(dedup,key=lambda x:(order[x['Source_Id']],{'TEMUAN_LINTAS_TINGKAT':0,'BELUM_DITEMUKAN':1,'KANDIDAT_OBJEK_SAMA':2}[x['Evidence_Type']],x['Found_Level'],x['Data_Source'],int(x['Rank'] or 0)))
ranks=collections.Counter()
for x in candidates:
 ranks[x['Source_Id']]+=1;x['Rank']=str(ranks[x['Source_Id']])
 if x['Evidence_Type']!='KANDIDAT_OBJEK_SAMA':assert not x['Candidate_Target_Id']
tables['Review_candidates.csv']=(list(candidates[0]),candidates)
headers,rows=tables['Cross_level_name_review.csv'];headers=headers+(['Reason'] if 'Reason' not in headers else [])
for x in rows:
 x['Candidate_Kecamatan_Target_Id']=''
 x['Reason']=f'Nama "{x["Source_Name"]}" ditemukan pada kelurahan dalam master. Tingkat wilayah berbeda dari objek kecamatan sumber; ID kandidat sengaja dikosongkan. Verifikasi lokasi dan tingkat wilayah yang dimaksud.'
tables['Cross_level_name_review.csv']=(headers,rows)
protected={'Object','Source_Id','Source_Name','Source_Parent_Id','Source_Direct_City_Id','Source_Direct_City_Resolved_Path','Source_Legacy_Kecamatans','Source_Postal_Code','Supplied_Name_Changes','Resolved_Parent_Path','Source_Parent_Display','Target_Id','Target_Name','Target_Provinsi','Target_KotaKabupaten','Target_Kecamatan','Target_Kelurahan','Target_Parent_Id','Id','Name','Provinsi__c','Kota_Kabupaten__c','Kecamatan__c','Original_Name','Original_Parent_Id','Original_Direct_City_Id','Master_Path','Parent_Target_Id','Master_Sheet_Id','Key','Postal_Codes','File','SHA256','Candidate_Name','Candidate_Path','Kelurahan_Master_Path','Candidate_Kecamatan_Path','Location_Examples'}
def translate(k,value):
 if k in protected:return value
 if value in V:return V[value]
 if k=='Notes':
  for en,idn in sorted(V.items(),key=lambda p:-len(p[0])):value=value.replace(en,idn)
 return value
translated={}
for name,(headers,rows) in tables.items():
 unknown=[h for h in headers if h not in H and h not in {'Id','Name','Provinsi__c','Kota_Kabupaten__c','Kecamatan__c'}];assert not unknown,(name,unknown)
 tr=[{H.get(k,k):translate(k,x.get(k,'')) for k in headers} for x in rows]
 translated[name]=tr
 with files[name].open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=[H.get(k,k) for k in headers]);w.writeheader();w.writerows(tr)
 # IDs, location names and original Salesforce API fields must not change during localization.
 for before,after in zip(rows,tr):
  for k in protected.intersection(headers):assert before.get(k,'')==after[H.get(k,k)]
# Readable, localized review workbook. CSV files are the source of truth.
sheets=[('Ringkasan','Summary.csv'),('Gap awal','Gap_invalid_summary.csv'),('Rekonsiliasi gap','Gap_analysis_reconciliation.csv'),('Kandidat tinjauan','Review_candidates.csv'),('Nama lintas tingkat','Cross_level_name_review.csv'),('Duplikat','Duplicate_repoint_proposals.csv'),('Masalah master','Master_data_issues.csv'),('Hierarki master ganda','Master_duplicate_paths.csv'),('Target belum pasti','Missing_or_unresolved_master_targets.csv')]+[(p+' perlu ditinjau',p+'_cleansing_mapping.csv') for p in PREFIX]
with pd.ExcelWriter(OUT/'Salesforce_cleansing_review.xlsx',engine='xlsxwriter',engine_kwargs={'options':{'strings_to_formulas':False,'strings_to_urls':False}}) as writer:
 for sheet,name in sheets:
  df=pd.DataFrame(translated[name],columns=[H.get(k,k) for k in tables[name][0]]);df.to_excel(writer,sheet_name=sheet[:31],index=False)
  ws=writer.sheets[sheet[:31]];ws.freeze_panes(1,0);ws.set_column(0,len(df.columns)-1,24);ws.autofilter(0,0,len(df),len(df.columns)-1)
# Indonesian folder guides, retaining paths and filenames for compatibility.
foldertext={
'00_Start_Here':('Mulai di sini','Ringkasan seluruh hasil. Angka pada file lain dapat saling tumpang tindih; jangan dijumlahkan antarfile.'),
'01_Update_Proposals':('Usulan pembaruan','Usulan perubahan nama atau lookup induk. Tinjau sebelum menyiapkan file upload yang hanya memuat Id dan kolom API yang disetujui. Kolom usulan kosong berarti tidak diubah, bukan dihapus.'),
'02_Duplicate_Handling':('Penanganan duplikat','Pemetaan Id sumber ke Id target. Verifikasi seluruh referensi sebelum memindahkannya. File ini bukan daftar upload atau penghapusan.'),
'03_Manual_Review':('Tinjauan manual','Daftar kerja cleansing, kandidat, serta temuan lintas tingkat. Temuan nama pada tingkat lain tidak membuktikan bahwa lokasinya sama. Semua ID kandidat lintas tingkat dikosongkan.'),
'04_Master_Targets':('Target dan masalah master','Inventaris master, target belum terverifikasi, masalah ID, dan hierarki ganda. Target belum pasti bukan berarti harus langsung membuat record baru.'),
'05_All_Records':('Seluruh record','Satu baris per record sumber, termasuk yang sudah valid. Gunakan sebagai referensi dan jejak pemeriksaan.'),
'06_Original_Gap_Analysis':('Analisis gap awal','Daftar dan hitungan dari analisis gap awal pengguna beserta rekonsiliasi terhadap pemeriksaan hierarki lengkap.'),
'07_Audit':('Audit','Checksum berkas masukan dan hasil validasi teknis. Bukan data untuk diunggah ke Salesforce.')}
for folder,(title,body) in foldertext.items():
 d=OUT/folder;d.mkdir(exist_ok=True);lines=['# '+title,'',body,'','| Berkas CSV | Jumlah baris data |','|---|---:|']
 for p in sorted(d.glob('*.csv')):lines.append(f'| [{p.name}]({p.name}) | {len(translated[p.name]):,} |')
 (d/'README.md').write_text('\n'.join(lines)+'\n')
rootlines=['# Panduan penggunaan CSV','','Paket berasal dari snapshot data 29 Oktober 2026. Tinjauan lintas tingkat dan penerjemahan diperbarui pada 30 Oktober 2026. Tidak ada perubahan pada Salesforce.','','Mulai dari `00_Start_Here/Summary.csv`. Nama file, folder, nama wilayah, ID dan kolom API Salesforce dipertahankan. Judul kolom laporan, status, alasan, catatan, dan panduan diterjemahkan ke Bahasa Indonesia.','','| Folder | Kegunaan |','|---|---|']
for folder,(title,body) in foldertext.items():rootlines.append(f'| {folder} | {title}: {body} |')
rootlines+=['','## Cara membaca temuan lintas tingkat','','- `Jenis_Bukti = TEMUAN_LINTAS_TINGKAT`: nama ditemukan pada tingkat wilayah lain. `Id_Target_Kandidat` selalu kosong.','- `Tingkat_Ditemukan`: provinsi, kota/kabupaten, kecamatan, atau kelurahan tempat nama muncul.','- `Sumber_Data = Master`: ditemukan dalam master wilayah.','- `Sumber_Data = Ekspor Salesforce`: ditemukan pada data Salesforce yang masih perlu diverifikasi.','- `Jumlah_Kemunculan` menghitung lokasi/nama yang berbeda, bukan jaminan kecocokan. `Contoh_Lokasi` dibatasi maksimal lima lokasi.','- Temuan di luar provinsi asal tetap ditampilkan sebagai bukti nama saja dan diberi catatan. Jangan menyamakan dua lokasi hanya berdasarkan namanya.','- Jika nama tidak ditemukan pada objek asal tetapi ditemukan pada tingkat lain, kandidat kemiripan lama diganti dengan bukti lintas tingkat tanpa ID.',
'- `KANDIDAT_OBJEK_SAMA` masih dapat memiliki ID usulan dari hasil sebelumnya; temuan ini berbeda dari bukti lintas tingkat.','- `BELUM_DITEMUKAN` berarti tidak ada nama sama setelah normalisasi; kandidat berbasis kemiripan belum membuktikan pemetaan.','','Pencarian lintas tingkat menggunakan kesamaan nama setelah normalisasi huruf besar/kecil, spasi, tanda baca, dan awalan administratif yang sesuai. Tidak menggunakan kecocokan sebagian kata. Penelusuran ini tidak mengubah keputusan update atau pemindahan referensi duplikat.','','## Kamus kolom laporan','','Kolom API `Id`, `Name`, `Provinsi__c`, `Kota_Kabupaten__c`, dan `Kecamatan__c` tetap memakai nama asli. Kolom laporan lainnya menggunakan padanan berikut.','','| Kolom sebelumnya | Kolom Bahasa Indonesia |','|---|---|']
rootlines += [f'| {k} | {v} |' for k,v in sorted(H.items())]
(OUT/'README.md').write_text('\n'.join(rootlines)+'\n')
# These JSON schemas are technical audit outputs; preserve their keys and analyzed snapshot values.
report={'kandidat_sebelumnya':len(old),'kandidat_sekarang':len(candidates),'sumber_dengan_temuan_lintas_tingkat':len({x['Source_Id'] for x in cross}),'baris_temuan_lintas_tingkat':len(cross),'sumber_belum_ditemukan':len({x['Source_Id'] for x in nohit}),'kandidat_inferensi_lintas_tingkat_lama_dihapus':removed,'kandidat_kemiripan_diganti_bukti_lintas_tingkat':suppressed,'semua_id_kandidat_lintas_tingkat_kosong':all(not x['Candidate_Target_Id'] for x in cross),'jumlah_record_sumber_tetap':sum(map(len,allrows)),'keputusan_update_dan_duplikat_tidak_diubah':True}
madura=[x for x in translated['Review_candidates.csv'] if x['Nama_Sumber'].casefold()=='madura']
assert madura and all(not x['Id_Target_Kandidat'] for x in madura if x['Jenis_Bukti']=='TEMUAN_LINTAS_TINGKAT')
(OUT/'07_Audit/Laporan_tinjauan_bahasa.md').write_text('# Validasi tinjauan dan penerjemahan\n\n'+'\n'.join(f'- {k}: {v}' for k,v in report.items())+'\n\nSeluruh nilai ID, nama wilayah, serta keputusan pada usulan update dan pemetaan duplikat dipertahankan. Pemeriksaan lintas tingkat hanya menambahkan bukti untuk ditinjau.\n')
print(json.dumps(report,indent=2));print(json.dumps(madura,indent=2,ensure_ascii=False))
