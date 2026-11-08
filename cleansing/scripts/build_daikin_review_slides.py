"""Two editable slides for Tim Daikin, from the current workbook snapshot."""
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
args=parser.parse_args()
ROOT=args.output_dir;ROOT.mkdir(parents=True,exist_ok=True)
SOURCE=args.workbook
SOURCE_REF=args.source_ref
SHA=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
STAMP=datetime.now(ZoneInfo('Asia/Jakarta')).strftime('%d November %Y')
wb=openpyxl.load_workbook(SOURCE,read_only=True)
summary=list(wb['RINGKASAN'].values);totals=[sum(r[i] for r in summary[1:]) for i in range(1,9)]
master,valid,changes,new,duplicate,unclear,pending,parent=totals
assert (valid,changes,new,duplicate,unclear,pending,parent)==(53478,8606,20511,3105,17117,1059,9000), "Refresh slide narrative for a new workbook snapshot"
assert sum([valid,changes,duplicate,unclear,parent])==91306
assert wb['DATA BELUM JELAS'].max_row==17118
ds=wb['DATA BELUM JELAS'];rows=ds.values;headers=next(rows);index={h:i for i,h in enumerate(headers)}
assert len(headers)==23 and 'Jumlah Rekomendasi Ditampilkan' not in headers
detail=Counter();source_ids=set();madura=None
for row in rows:
 rid=row[index['Id Sumber']];assert rid not in source_ids;source_ids.add(rid)
 has_id=bool(row[index['Rekomendasi 1 ID Salesforce']])
 has_location=bool(row[index['Rekomendasi 1 Lokasi']])
 if has_id and ';' in row[index['Rekomendasi 1 ID Salesforce']]:detail['multiple_ids']+=1
 detail['id_available' if has_id else 'id_blank']+=1
 if not has_id:detail['location_without_id' if has_location else 'no_recommendation']+=1
 if rid=='a1oJ40000009JPKIA2':madura=row
assert (detail['id_available'],detail['location_without_id'],detail['no_recommendation'],detail['id_blank'])==(11485,3604,2028,5632)
assert madura is not None and not madura[index['Rekomendasi 1 ID Salesforce']] and not madura[index['Rekomendasi 1 Lokasi']]
assert len(source_ids)==unclear
ps=wb['PERBAIKAN PARENT - ID TETAP'];rows=ps.values;ph=next(rows);pi={h:i for i,h in enumerate(ph)}
assert 'Relasi Master yang Seharusnya' in pi
parent_ids=set();relation_keys=set();relation_count=0
for row in rows:
 rid=row[pi['Id Data']];key=(rid,row[pi['Hubungan yang Diperiksa']])
 assert key not in relation_keys;relation_keys.add(key);parent_ids.add(rid);relation_count+=1
 assert row[pi['Relasi Master yang Seharusnya']]
assert len(parent_ids)==parent and relation_count==12570
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
       '91.306 data Salesforce dikelompokkan untuk review; 20.511 calon lokasi baru diperiksa terpisah.')
rect(s,.55,1.88,3.67,3.65,'white')
txt(s,.74,2.04,3.29,.22,'KOMPOSISI DATA SALESFORCE',10,'muted',True,PP_ALIGN.CENTER)
labels=['Valid wilayah','Perlu diubah','Parent ID tetap','Data belum jelas','Duplikat']
values=[valid,changes,parent,unclear,duplicate];colors=['teal','blue','purple','amber','coral']
data=ChartData();data.categories=labels;data.add_series('Jumlah data Salesforce',values)
chart=s.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT,Inches(.78),Inches(2.41),Inches(3.18),Inches(2.55),data).chart
chart.has_legend=False;chart.has_title=False;plot=chart.plots[0]
plot.hole_size=77;plot.first_slice_angle=270;plot.has_data_labels=False
for point,color in zip(chart.series[0].points,colors):
 point.format.fill.solid();point.format.fill.fore_color.rgb=rgb(color);point.format.line.fill.background()
txt(s,1.29,3.38,2.17,.37,'91.306',20,'ink',True,PP_ALIGN.CENTER)
txt(s,1.29,3.85,2.17,.23,'data sumber',10.5,'muted',False,PP_ALIGN.CENTER)
txt(s,.76,5.02,3.25,.30,'Setiap ID berada di satu kelompok.',10.5,'muted',False,PP_ALIGN.CENTER)
rect(s,4.43,1.88,8.35,.43,'ink')
txt(s,4.62,1.98,2.33,.22,'KELOMPOK',10,'white',True)
txt(s,6.87,1.98,1.06,.22,'JUMLAH',10,'white',True,PP_ALIGN.RIGHT)
txt(s,8.18,1.98,4.35,.22,'PENJELASAN / KEPUTUSAN TIM DAIKIN',10,'white',True)
descs=['Nama dan Parent sesuai; sebagian masih\nmemerlukan konfirmasi ID acuan.',
       'Konfirmasi usulan perubahan nama,\nParent, atau kabupaten/kota langsung.',
       '9.000 ID unik; 12.570 baris hubungan.\nPeriksa relasi usulan dan lokasi master.',
       'Pastikan tingkat wilayah, lokasi, provinsi,\ndan ID tujuan yang benar.',
       'Pilih ID yang dipertahankan; periksa dan\npindahkan referensi sebelum nonaktifkan.']
for i,(label,value,color,desc) in enumerate(zip(labels,values,colors,descs)):
 y=2.31+i*.644
 rect(s,4.43,y,8.35,.614,'white');rect(s,4.43,y,.045,.614,color)
 txt(s,4.62,y+.18,2.18,.30,label,13,color,True)
 txt(s,6.84,y+.15,1.13,.33,fmt(value),17,color,True,PP_ALIGN.RIGHT)
 txt(s,8.18,y+.12,4.38,.43,desc,12,'ink')
rect(s,.55,5.70,12.23,.98,'soft_blue')
txt(s,.73,5.84,2.25,.61,'DATA BELUM JELAS\n17.117 data',12,'blue',True)
for x,n,msg,color in [(3.08,detail['id_available'],'ID rekomendasi tersedia','blue'),(6.35,detail['location_without_id'],'Lokasi ada; ID belum pasti','amber'),(9.62,detail['no_recommendation'],'Belum ada rekomendasi','coral')]:
 txt(s,x,5.82,2.96,.32,fmt(n),19,color,True)
 txt(s,x,6.24,2.96,.23,msg,11,'ink')
txt(s,3.08,6.50,9.45,.16,f"Dari kelompok ber-ID, {fmt(detail['multiple_ids'])} data memuat beberapa ID; pilih satu ID final setelah dikonfirmasi.",9,'muted')
txt(s,.57,6.81,12.20,.18,'Catatan: 1.059 menunggu ID acuan sudah termasuk data valid. ID rekomendasi kosong: 5.632 = 3.604 + 2.028.',10,'muted')
notes(s,'Sumber workbook SHA-256 '+SHA+'. Lima kelompok chart saling lepas berdasarkan ID sumber, total 91.306: valid 53.478; perubahan 8.606; Parent ID tetap 9.000 ID unik dalam 12.570 baris hubungan; belum jelas 17.117; duplikat 3.105. Valid termasuk 1.059 kelurahan yang nama serta hubungan Parent sudah sesuai, tetapi ID acuan mapping masih perlu persetujuan. Angka ini bukan tambahan. Calon data baru 20.511 menghitung lokasi master, bukan data Salesforce; perlu dicari data lama dan dikonfirmasi sebelum insert. DATA BELUM JELAS: 11.485 memiliki ID rekomendasi pertama, 3.604 memiliki rekomendasi lokasi tetapi ID pertama kosong, 2.028 tanpa rekomendasi; jumlah sel ID kosong 5.632. Tujuh rekomendasi yang berbeda penanda wilayah sudah dikosongkan. Sebanyak 855 data kini memiliki bukti nama pada master, tetapi lokasinya masih perlu dikonfirmasi. Sebanyak 424 data mempunyai kandidat lain ber-ID; ID itu tidak otomatis menggantikan rekomendasi pertama. Madura tidak mendapat rekomendasi Kab. Madiun atau Kota Madiun. Kolom Jumlah Rekomendasi Ditampilkan telah dihapus; kelompok dihitung langsung dari nama/lokasi/ID rekomendasi. Parent ID tetap: 9.000 data, 3.570 di antaranya mempunyai dua hubungan yang perlu diperiksa. Barisnya terdiri atas 200 Parent Kabupaten/Kota, 8.543 Parent Kecamatan, 3.827 Kabupaten/Kota Langsung. ID yang sama tidak otomatis berarti valid. Sheet Parent tidak mempunyai irisan ID dengan 8.606 data pada tiga sheet PERUBAHAN. Semua angka dibaca dari workbook terbaru; belum ada persetujuan atau update Salesforce otomatis.')

s=base(2,'Langkah review: periksa lokasi, lalu putuskan ID',
       'Gunakan kolom keputusan dan catatan yang tersedia. ID yang belum dapat dipastikan tetap dikosongkan.')
def step(n,y,title,body,h=.57):
 rect(s,.55,y,.37,.37,'blue');txt(s,.55,y+.035,.37,.29,str(n),16,'white',True,PP_ALIGN.CENTER)
 txt(s,1.08,y+.015,3.28,.52,title,15,'ink',True)
 txt(s,4.52,y+.015,8.18,h,body,12.3,'ink')
step(1,1.86,'Baca RINGKASAN & PETUNJUK','Pahami kelompok data dan wilayah acuannya. Pastikan perbedaan kota/kabupaten,\nkecamatan, kelurahan, serta provinsi sebelum memilih tujuan.')
rect(s,.55,2.55,.37,.37,'blue');txt(s,.55,2.585,.37,.29,'2',16,'white',True,PP_ALIGN.CENTER)
txt(s,1.08,2.57,11.6,.35,'Buka sheet sesuai kasus dan lakukan pemeriksaan berikut',15,'ink',True)
cards=[('VALID KELURAHAN • 1.059','Filter J: “Penetapan ID utama”.\nIsi keputusan & ID final; lengkapi\ncatatan, PIC, tanggal (kolom M–Q).','teal'),
       ('PERUBAHAN • 8.606','Bandingkan nama dan Parent saat ini\ndengan usulannya. Setujui atau\nkoreksi nilai yang perlu diubah.','blue'),
       ('PARENT ID TETAP • 9.000 ID unik','Baca tiap baris hubungan & relasi master.\nKonfirmasi ID relasi usulan; lokasi/nama\nyang belum pasti diperiksa di catatan.','purple'),
       ('DATA BELUM JELAS • 17.117','Usulan Muara: ID belum dipastikan.\nPeriksa lokasi dan alasan ID kosong;\npastikan ID tujuan sebelum dipilih.','amber'),
       ('DATA DUPLIKAT • 3.105','Pilih ID yang dipertahankan.\nPeriksa referensi data anak sebelum\nmenyetujui penonaktifan duplikat.','coral'),
       ('CALON DATA BARU • 20.511 lokasi','Cari data lama; jika ada, isi ID-nya.\nJika belum, konfirmasi pembuatan\ndata beserta nama dan Parent.','blue')]
for i,(title,body,color) in enumerate(cards):
 x=.55+(i%3)*4.14;y=3.06+(i//3)*1.07
 rect(s,x,y,3.94,1.00,'white');rect(s,x,y,.04,1.00,color)
 txt(s,x+.14,y+.11,3.65,.23,title,10.4,color,True)
 txt(s,x+.14,y+.38,3.65,.59,body,11.2,'ink')
step(3,5.30,'Periksa bukti pendukung','Misool Utara/Selatan: nama beda arah. Sukarindik: Parent berbeda dari master.\nKonfirmasi lokasi pada kasus seperti ini; nama mirip belum cukup untuk memilih ID.')
step(4,5.95,'Isi hasil keputusan','Isi kolom kuning: keputusan, ID final jika diminta, catatan, PIC, dan tanggal.\nSel merah berarti isian belum lengkap; periksa sebelum hasil dikirim.')
step(5,6.50,'Kirim hasil review','Serahkan workbook kepada tim cleansing. File untuk perubahan Salesforce\ndisiapkan terpisah setelah keputusan disetujui.',.43)
notes(s,'Nama sheet lengkap: PERUBAHAN KOTA, PERUBAHAN KECAMATAN, PERUBAHAN KELURAHAN; PERBAIKAN PARENT - ID TETAP; DATA BELUM JELAS; DATA DUPLIKAT; CALON DATA BARU. Filter 1.059 valid pending: VALID KELURAHAN, kolom J Alasan Dinyatakan Sesuai, Filter Teks > Berisi > Penetapan ID utama. Nama dan hubungan Parent sudah sesuai; keputusan ID acuan ditulis di kolom M Keputusan Tim Daikin, N Id Utama Final Tim Daikin, O Catatan Tim Daikin, P PIC Tim Daikin, Q Tanggal Konfirmasi. Lima kolom ini hanya diisi untuk 1.059 data yang menunggu ID utama. Sheet Parent kini 19 kolom, satu baris per hubungan yang perlu diperiksa. ID sumber boleh berulang untuk hubungan berbeda; hitung 9.000 ID unik, bukan 12.570 baris sebagai data berbeda. Kolom D Hubungan yang Diperiksa, E Id Relasi Sekarang, H Id Relasi Usulan, J Relasi Master yang Seharusnya (provinsi hingga nama data), L Status Review, O Keputusan Tim Daikin, P Id Relasi Final Tim Daikin, Q Catatan Tim Daikin, R PIC Tim Daikin, S Tanggal Konfirmasi. Jika master menampilkan beberapa pilihan lokasi, pastikan dahulu lokasi yang benar; jangan mengisi ID berdasarkan nama saja. DATA BELUM JELAS kini 23 kolom tanpa Jumlah Rekomendasi Ditampilkan: Q Keputusan Tim Daikin, R Id Target Final Tim Daikin, S Nama Final Tim Daikin, T Id Parent Final Tim Daikin, U Catatan Tim Daikin, V PIC Tim Daikin, W Tanggal Konfirmasi. Tetapkan keputusan dan ID/nama/Parent final jika diminta, disertai catatan, PIC dan tanggal pada semua sheet yang memiliki kolom input tersebut. Bukti lintas tingkat tidak menjadi mapping otomatis. CALON DATA BARU diperiksa terhadap data lama sebelum persetujuan insert. Semua ID final yang belum diketahui tetap kosong. File upload disusun terpisah setelah review; workbook tidak mengubah Salesforce otomatis.')

assert len(prs.slides)==2
for page,sh,value,size in TEXT:
 assert sh.left>=0 and sh.top>=0 and sh.left+sh.width<=prs.slide_width and sh.top+sh.height<=prs.slide_height,(page,value)
path=ROOT/'Daikin_Ringkasan_dan_Panduan_Review_Terbaru_2_Slide.pptx';prs.save(path)
assert SHA==hashlib.sha256(SOURCE.read_bytes()).hexdigest()
(ROOT/'source_and_counts.json').write_text(json.dumps({'source':str(SOURCE),'source_ref':SOURCE_REF,'sha256':SHA,
 'source_records':91306,'master_locations':master,'valid':valid,'valid_pending_id_subset':pending,
 'changes':changes,'parent_same_id':parent,'unclear':unclear,'duplicate':duplicate,'new_locations':new,
 'unclear_first_id_available':detail['id_available'],'unclear_location_without_id':detail['location_without_id'],
 'unclear_no_recommendation':detail['no_recommendation'],'unclear_first_id_blank':detail['id_blank'],'unclear_multiple_ids':detail['multiple_ids'],
 'parent_relationship_rows':relation_count,'parent_unique_ids':len(parent_ids)},ensure_ascii=False,indent=2))
print(path)
