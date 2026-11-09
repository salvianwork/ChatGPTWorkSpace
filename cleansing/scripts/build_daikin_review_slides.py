"""Build two editable review slides from the merged Daikin PERUBAHAN workbook."""
from pathlib import Path
import argparse,hashlib,json
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
import openpyxl
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.enum.chart import XL_CHART_TYPE
from pptx.chart.data import ChartData
from pptx.dml.color import RGBColor

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--workbook',type=Path,required=True)
parser.add_argument('--output-dir',type=Path,required=True)
parser.add_argument('--source-ref',default='cleansing/service-territory-review-2026-10-29')
args=parser.parse_args();ROOT=args.output_dir;ROOT.mkdir(parents=True,exist_ok=True)
SOURCE=args.workbook;SOURCE_REF=args.source_ref;SHA=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
now=datetime.now(ZoneInfo('Asia/Bangkok'))
months=['','Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember']
STAMP=f'{now.day:02} {months[now.month]} {now.year}'
wb=openpyxl.load_workbook(SOURCE,read_only=True)
assert len(wb.sheetnames)==14 and 'PERBAIKAN PARENT - ID TETAP' not in wb.sheetnames
summary=list(wb['RINGKASAN'].values)
master,valid,changes,new,duplicate,unclear,pending=[sum(r[i] for r in summary[1:]) for i in range(1,8)]
assert min(valid,changes,new,duplicate,unclear,pending)>=0 and pending<=valid
assert valid+changes+duplicate+unclear==91306
change_ids=set();change_keys=set();change_rows=0;pending_values=0;pending_locations=0;per_sheet={}
for title in ['PERUBAHAN KOTA','PERUBAHAN KECAMATAN','PERUBAHAN KELURAHAN']:
 rows=wb[title].values;h=next(rows);ix={k:i for i,k in enumerate(h)};n=0;ids=set()
 for row in rows:
  rid=row[ix['Id Data']];key=rid,row[ix['Bagian yang Diubah']]
  assert key not in change_keys;change_keys.add(key);change_ids.add(rid);ids.add(rid);n+=1;change_rows+=1
  assert row[ix['Relasi Master yang Seharusnya']]
  pending_values+=not row[ix['Nilai Usulan']]
  pending_locations+='lokasi' in row[ix['Status Konfirmasi']].casefold()
 per_sheet[title]={'source_ids':len(ids),'review_rows':n}
assert len(change_ids)==changes and change_rows>=changes
rows=wb['DATA BELUM JELAS'].values;h=next(rows);ix={k:i for i,k in enumerate(h)};detail=Counter();data_ids=set()
for row in rows:
 rid=row[ix['Id Sumber']];assert rid not in data_ids;data_ids.add(rid)
 has_id=bool(row[ix['Rekomendasi ID Salesforce']]);location=bool(row[ix['Rekomendasi Lokasi']])
 detail['id_available' if has_id else 'id_blank']+=1
 if not has_id:detail['location_without_id' if location else 'no_recommendation']+=1
 if has_id and ';' in row[ix['Rekomendasi ID Salesforce']]:detail['multiple_ids']+=1
assert len(data_ids)==unclear and not data_ids&change_ids
assert detail['id_available']+detail['id_blank']==unclear
assert detail['location_without_id']+detail['no_recommendation']==detail['id_blank']
duplicate_ids=set();duplicate_statuses=Counter()
rows=wb['DATA DUPLIKAT'].values;h=next(rows);di={k:i for i,k in enumerate(h)}
for row in rows:
 rid=row[di['Id Duplikat']];assert rid not in duplicate_ids;duplicate_ids.add(rid)
 assert rid!=row[di['Id Yang Dipertahankan']]
 duplicate_statuses[row[di['Status Konfirmasi']]]+=1
assert len(duplicate_ids)==duplicate and not duplicate_ids&(data_ids|change_ids)
wb.close()
URL='https://github.com/salvianwork/ChatGPTWorkSpace/blob/'+SOURCE_REF+'/cleansing/client_review/Mandatory%20for%20Client/Daikin_Cleansing_Data_Regional.xlsx'
COL={'ink':'153447','muted':'59707E','bg':'F3F7FA','white':'FFFFFF','line':'DCE7EE',
     'blue':'0075BA','teal':'138D83','purple':'7763A8','amber':'AF7313','coral':'C65B43',
     'soft_blue':'E6F2FA','soft_teal':'E5F4F0','soft_amber':'FBF1DD','soft_purple':'F0EDF8'}
prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
prs.core_properties.title='Daikin | Ringkasan Temuan dan Panduan Review Regional'
prs.core_properties.author='Tim Review Data Regional'
prs.core_properties.subject='Dua slide: temuan terbaru dan langkah review Tim Daikin'
prs.core_properties.comments='Sumber workbook SHA-256 '+SHA+'; workbook tidak diubah.'
TEXT=[]
def rgb(key):return RGBColor.from_string(COL.get(key,key))
def rect(s,x,y,w,h,color):
 sh=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x),Inches(y),Inches(w),Inches(h))
 sh.fill.solid();sh.fill.fore_color.rgb=rgb(color);sh.line.fill.background()
 for e in sh._element.xpath('./p:style/a:effectRef'):e.set('idx','0')
 return sh
def txt(s,x,y,w,h,value,size=14,color='ink',bold=False,align=None):
 sh=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));tf=sh.text_frame
 tf.clear();tf.word_wrap=True;tf.margin_left=tf.margin_right=0;tf.margin_top=tf.margin_bottom=0
 for i,line in enumerate(value.split('\n')):
  p=tf.paragraphs[0] if i==0 else tf.add_paragraph();p.text=line
  p.line_spacing=1.08;p.space_after=Pt(2 if i<len(value.split('\n'))-1 else 0)
  if align is not None:p.alignment=align
  for run in p.runs:
   run.font.name='DejaVu Sans';run.font.size=Pt(size);run.font.bold=bold;run.font.color.rgb=rgb(color)
   run._r.get_or_add_rPr().set('lang','id-ID')
 TEXT.append((len(prs.slides),sh,value,size));return sh
def base(n,title,subtitle):
 s=prs.slides.add_slide(prs.slide_layouts[6]);s.background.fill.solid();s.background.fill.fore_color.rgb=rgb('bg')
 rect(s,0,0,13.333,.07,'blue')
 txt(s,.55,.25,12.2,.22,'DAIKIN  /  REVIEW DATA REGIONAL',10,'blue',True)
 txt(s,.55,.64,12.25,.55,title,27,'ink',True)
 txt(s,.55,1.29,12.2,.38,subtitle,12.5,'muted')
 rect(s,.55,7.07,12.23,.012,'line')
 sh=txt(s,.55,7.19,11.4,.16,'Sumber: Daikin_Cleansing_Data_Regional.xlsx  •  '+'Excel '+SHA[:10]+'  •  '+STAMP,8.5,'muted')
 for p in sh.text_frame.paragraphs:
  for r in p.runs:r.hyperlink.address=URL
 txt(s,12.05,7.17,.72,.20,f'{n:02} / 02',9,'blue',True,PP_ALIGN.RIGHT)
 return s
def notes(s,value):s.notes_slide.notes_text_frame.text=value+'\n\nSumber: '+URL+'\nSHA-256: '+SHA
def fmt(n):return f'{n:,}'.replace(',','.')

s=base(1,'Ringkasan temuan & keputusan yang diperlukan',
       f'{fmt(91306)} data Salesforce dikelompokkan untuk review; {fmt(new)} calon lokasi baru diperiksa terpisah.')
rect(s,.55,1.88,3.67,3.65,'white')
txt(s,.74,2.04,3.29,.22,'KOMPOSISI DATA SALESFORCE',10,'muted',True,PP_ALIGN.CENTER)
labels=['Valid wilayah','Review perubahan','Data belum jelas','Duplikat']
values=[valid,changes,unclear,duplicate];colors=['teal','blue','amber','coral']
data=ChartData();data.categories=labels;data.add_series('Jumlah data Salesforce',values)
chart=s.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT,Inches(.78),Inches(2.41),Inches(3.18),Inches(2.55),data).chart
chart.has_legend=False;chart.has_title=False;plot=chart.plots[0]
plot.hole_size=77;plot.first_slice_angle=270;plot.has_data_labels=False
for point,color in zip(chart.series[0].points,colors):
 point.format.fill.solid();point.format.fill.fore_color.rgb=rgb(color);point.format.line.fill.background()
txt(s,1.29,3.38,2.17,.37,fmt(91306),20,'ink',True,PP_ALIGN.CENTER)
txt(s,1.29,3.85,2.17,.23,'data sumber',10.5,'muted',False,PP_ALIGN.CENTER)
txt(s,.76,5.02,3.25,.30,'Setiap ID berada di satu kelompok.',10.5,'muted',False,PP_ALIGN.CENTER)
rect(s,4.43,1.88,8.35,.43,'ink')
txt(s,4.62,1.98,2.33,.22,'KELOMPOK',10,'white',True)
txt(s,6.87,1.98,1.06,.22,'JUMLAH',10,'white',True,PP_ALIGN.RIGHT)
txt(s,8.18,1.98,4.35,.22,'PENJELASAN / KEPUTUSAN TIM DAIKIN',10,'white',True)
descs=['Nama dan Parent sesuai; sebagian masih\nmemerlukan konfirmasi ID utama.',
       f'{fmt(changes)} ID unik; {fmt(change_rows)} baris review.\nKonfirmasi nama, Parent, dan lokasi.',
       'Pastikan tingkat wilayah, lokasi, provinsi,\ndan ID tujuan yang benar.',
       'Kecocokan kuat; konfirmasi ejaan, ID tujuan,\ndan referensi anak sebelum digabung.']
for i,(label,value,color,desc) in enumerate(zip(labels,values,colors,descs)):
 y=2.31+i*.805
 rect(s,4.43,y,8.35,.775,'white');rect(s,4.43,y,.045,.775,color)
 txt(s,4.62,y+.25,2.18,.30,label,13,color,True)
 txt(s,6.84,y+.22,1.13,.33,fmt(value),17,color,True,PP_ALIGN.RIGHT)
 txt(s,8.18,y+.20,4.38,.46,desc,12,'ink')
rect(s,.55,5.70,12.23,.98,'soft_blue')
txt(s,.73,5.84,2.25,.61,f'DATA BELUM JELAS\n{fmt(unclear)} data',12,'blue',True)
for x,n,msg,color in [(3.08,detail['id_available'],'ID rekomendasi tersedia','blue'),(6.35,detail['location_without_id'],'Lokasi ada; ID belum pasti','amber'),(9.62,detail['no_recommendation'],'Belum ada rekomendasi','coral')]:
 txt(s,x,5.82,2.96,.32,fmt(n),19,color,True);txt(s,x,6.24,2.96,.23,msg,11,'ink')
txt(s,3.08,6.50,9.45,.16,f"Dari kelompok ber-ID, {fmt(detail['multiple_ids'])} data memuat beberapa ID; pilih satu ID final setelah dikonfirmasi.",9,'muted')
txt(s,.57,6.81,12.20,.18,f"Catatan: {fmt(pending)} menunggu ID utama sudah termasuk data valid. ID rekomendasi kosong: {fmt(detail['id_blank'])} = {fmt(detail['location_without_id'])} + {fmt(detail['no_recommendation'])}.",10,'muted')
notes(s,f'Grafik menghitung ID Salesforce unik: valid {valid}; review perubahan {changes}; belum jelas {unclear}; duplikat {duplicate}, total 91.306. Seluruh perbaikan nama dan Parent berada di PERUBAHAN sesuai objek. {changes} data mempunyai {change_rows} baris perubahan/hubungan. Satu ID boleh berulang untuk beberapa bagian; keputusan diberikan per baris. Sebanyak {pending_values} baris belum memiliki nilai usulan dan {pending_locations} baris memerlukan konfirmasi lokasi. Angka ini menghitung baris dan dapat saling beririsan. Jumlah master {master} serta calon data baru {new} menghitung lokasi, bukan data Salesforce. Sebanyak {pending} data menunggu ID utama sudah termasuk valid. DATA BELUM JELAS tetap: ID pertama tersedia {detail["id_available"]}, lokasi ada tanpa ID pertama {detail["location_without_id"]}, tanpa rekomendasi {detail["no_recommendation"]}; ID pertama kosong {detail["id_blank"]}. Sebanyak {detail["multiple_ids"]} data ber-ID memerlukan pemilihan satu ID akhir. Tidak ada persetujuan atau perubahan Salesforce otomatis.')

s=base(2,'Langkah review: satu keputusan per perubahan',
       'Gunakan kolom kuning. Pilih perbaikan atau penggabungan sesuai status dan bukti lokasi.')
def step(n,y,title,body,h=.57):
 rect(s,.55,y,.37,.37,'blue');txt(s,.55,y+.035,.37,.29,str(n),16,'white',True,PP_ALIGN.CENTER)
 txt(s,1.08,y+.015,3.28,.52,title,15,'ink',True);txt(s,4.52,y+.015,8.18,h,body,12.3,'ink')
step(1,1.86,'Baca RINGKASAN & PETUNJUK','Pahami kelompok data dan wilayah acuannya. Bedakan jumlah ID data\ndengan jumlah baris yang harus direview; satu ID bisa memiliki beberapa baris.')
rect(s,.55,2.55,.37,.37,'blue');txt(s,.55,2.585,.37,.29,'2',16,'white',True,PP_ALIGN.CENTER)
txt(s,1.08,2.57,11.6,.35,'Buka sheet sesuai kasus dan lakukan pemeriksaan berikut',15,'ink',True)
cards=[(f'VALID KELURAHAN • {fmt(pending)}','Filter J: “Penetapan ID utama”.\nIsi keputusan & ID final; lengkapi\ncatatan, PIC, tanggal (kolom M–Q).','teal'),
       (f'PERUBAHAN • {fmt(changes)} data','Baca bagian yang diubah dan usulannya.\nPutuskan setiap baris Nama, Parent,\natau Kabupaten/Kota Langsung.','blue'),
       ('CONTOH • HUTAGURGUR','Dua baris: Parent kecamatan dan\nkabupaten/kota langsung. Keputusan\nsalah satu tidak menyetujui lainnya.','purple'),
       (f'DATA BELUM JELAS • {fmt(unclear)}','Kalimantan Tengah | Kab. Barito Selatan | Dusun Selatan | Buntok Kota\nRekomendasi: Dusun Selatan.','amber'),
       (f'DATA DUPLIKAT • {fmt(duplicate)}','Baca status, alasan, dan lokasi master.\nKonfirmasi ID tujuan; isi M–Q.\nPeriksa Parent tujuan & referensi anak.','coral'),
       (f'CALON DATA BARU • {fmt(new)} lokasi','Cari data lama; jika ada, isi ID-nya.\nJika belum, konfirmasi pembuatan\ndata beserta nama dan Parent.','blue')]
for i,(title,body,color) in enumerate(cards):
 x=.55+(i%3)*4.14;y=3.06+(i//3)*1.07
 rect(s,x,y,3.94,1.00,'white');rect(s,x,y,.04,1.00,color)
 txt(s,x+.14,y+.11,3.65,.23,title,10.4,color,True);txt(s,x+.14,y+.38,3.65,.59,body,10.8,'ink')
step(3,5.30,'Periksa bukti & status','PERUBAHAN: ID tetap. DATA DUPLIKAT: periksa usulan penggabungan dengan bukti kuat.\nDATA BELUM JELAS: pastikan lokasi dan ID. Review Parent tujuan sebelum penggabungan.')
step(4,5.95,'Isi hasil keputusan','PERUBAHAN: keputusan N, nilai final O, lokasi final P; catatan, PIC, tanggal Q–S.\nLengkapi sel merah. Baris Nama diisi nama; baris hubungan diisi ID Salesforce.')
step(5,6.50,'Kirim hasil review','Filter keputusan kosong untuk melihat pekerjaan tersisa. Tim cleansing menyiapkan\nfile perubahan Salesforce setelah keputusan disetujui.',.43)
notes(s,'PERUBAHAN KOTA, PERUBAHAN KECAMATAN, dan PERUBAHAN KELURAHAN mempunyai 19 kolom yang sama: A Objek, B Id Data, C Nama Data, D Bagian yang Diubah, E Nilai Sekarang, F Nama Relasi Sekarang, G Konteks Lokasi Sekarang, H Nilai Usulan, I Nama Relasi Usulan, J Relasi Master yang Seharusnya, K Status Konfirmasi, L Penjelasan dan Tindakan, M Temuan Pada Tingkat Lain, N Keputusan Tim Daikin, O Nilai Final Tim Daikin, P Lokasi Final Tim Daikin, Q Catatan Tim Daikin, R PIC Tim Daikin, S Tanggal Konfirmasi. Baris Nama memakai nama pada nilai sekarang/usulan/final; baris hubungan memakai ID relasi. Satu baris tidak mengubah ID data. Setujui usulan hanya tersedia jika nilai dan lokasi cukup jelas. Gunakan nilai final memerlukan O; lokasi yang belum pasti juga memerlukan P berisi urutan provinsi hingga data. Tolak usulan atau Perlu diskusi memerlukan catatan. PIC dan tanggal diisi per keputusan. Hutagurgur mempunyai dua hubungan yang diputuskan secara terpisah; Parent kecamatan belum mempunyai ID usulan, sedangkan kabupaten/kota langsung mempunyai ID usulan. Sebanyak 132 data juga memperoleh baris Nama terpisah untuk konfirmasi yang sudah ada sebelumnya. Konfirmasi nama tidak otomatis disetujui oleh keputusan Parent. Pada VALID KELURAHAN, filter J berisi Penetapan ID utama lalu isi M–Q. Pada DATA BELUM JELAS, judul rekomendasi tidak bernomor. Bukti master Buntok adalah Kalimantan Tengah | Kab. Barito Selatan | Dusun Selatan | Buntok Kota; rekomendasi kecamatannya Dusun Selatan. Bukti lintas tingkat menampilkan struktur lokasi tanpa awalan label tingkat wilayah dan tetap memisahkan Master serta ekspor Salesforce. DATA BELUM JELAS dan PILIHAN MAPPING tetap dipakai untuk memilih ID tujuan setelah lokasi diketahui. File review tidak mengubah Salesforce otomatis.')
notes(s,s.notes_slide.notes_text_frame.text+'\nDATA DUPLIKAT: G Status Konfirmasi, H Alasan Usulan, M Keputusan Tim Daikin, N Id Tujuan Final, O Catatan, P PIC, Q Tanggal. Dugaan beda satu huruf tetap memerlukan konfirmasi ejaan. Bontolanra dan Pajar Indah cocok dengan variasi nama pada master dalam Parent yang sama. Untuk Pajar Indah, master adalah Sumatra Selatan | Kab. Muara Enim | Gunung Megang | Pajar Indah (Fajar Indah). Parent tujuan sudah Gunung Megang. Jika sumber digabung, tidak perlu mengisi Parent sumber sebagai tindakan kedua. Tidak ada penggabungan atau persetujuan otomatis.')

assert len(prs.slides)==2
for page,sh,value,size in TEXT:
 assert sh.left>=0 and sh.top>=0 and sh.left+sh.width<=prs.slide_width and sh.top+sh.height<=prs.slide_height,(page,value)
path=ROOT/'Daikin_Ringkasan_dan_Panduan_Review_Terbaru_2_Slide.pptx';prs.save(path)
assert SHA==hashlib.sha256(SOURCE.read_bytes()).hexdigest()
(ROOT/'source_and_counts.json').write_text(json.dumps({'source':str(SOURCE),'source_ref':SOURCE_REF,'sha256':SHA,
 'source_records':91306,'master_locations':master,'valid':valid,'valid_pending_id_subset':pending,'changes':changes,
 'change_review_rows':change_rows,'changes_by_sheet':per_sheet,'pending_change_values':pending_values,
 'pending_change_locations':pending_locations,'unclear':unclear,'duplicate':duplicate,'new_locations':new,
 'unclear_first_id_available':detail['id_available'],'unclear_location_without_id':detail['location_without_id'],
 'unclear_no_recommendation':detail['no_recommendation'],'unclear_first_id_blank':detail['id_blank'],
 'unclear_multiple_ids':detail['multiple_ids'],'duplicate_statuses':dict(duplicate_statuses)},ensure_ascii=False,indent=2))
print(path)
