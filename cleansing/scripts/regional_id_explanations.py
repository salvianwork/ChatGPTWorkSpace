"""Read-only explanations of missing IDs and repairs on an existing source ID."""
from collections import defaultdict
from regional_matching import normalize

ID_NOTE_FIELDS={'Client_ID_Note':'Penjelasan_ID_Client'}
LEVELS=['provinsi','kabupaten/kota','kecamatan','kelurahan']


class IDExplanation:
    def __init__(self,records_by_level,target_ids):
        self.records=records_by_level
        self.targets=target_ids
        self.byname=[]
        for level,records in enumerate(records_by_level):
            names=defaultdict(list)
            for record in records.values():names[normalize(record['Source_Name'],level)].append(record)
            self.byname.append(names)

    def parent_location(self,record,level):
        """Describe the record actually referenced by its current lookup ID.

        Never substitute a path recovered from text for the actual lookup.
        Resolved names are used only when that parent needs no relationship review.
        """
        pid=record.get('Source_Parent_Id','')
        if not pid:return f'kolom {LEVELS[level-1]} utama masih kosong'
        parent=self.records[level-1].get(pid)
        if parent is None:return f'ID {LEVELS[level-1]} {pid} tidak ditemukan di file Salesforce'
        path=parent.get('_path')
        if path and not parent.get('_blocked') and not parent.get('_requires_review'):
            return f'{LEVELS[level-1]} saat ini: '+ ' | '.join(path)
        return (f'{LEVELS[level-1]} pada file bernama {parent["Source_Name"]} (ID {pid}); '
                'lokasi lengkap dan hubungannya masih perlu dikonfirmasi')

    def missing_location_id(self,path):
        """Name equality supplies evidence for a note, never a destination ID."""
        level=len(path)-1;label=LEVELS[level];name=path[-1]
        found=self.byname[level].get(normalize(name,level),[])
        heading=f'Alasan ID {label} {name} belum dipastikan:'
        if not found:
            return (heading+f'\n• Nama {name} ada di master, tetapi data bernama sama pada tingkat {label} '
                    'tidak ditemukan di file Salesforce yang diperiksa.\n'
                    'Tindak lanjut: telusuri nama atau ID lain. Pembuatan data baru perlu persetujuan client setelah pemeriksaan data lama.')
        matching=[r for r in found if r.get('_path')==path and not r.get('_blocked') and not r.get('_requires_review')]
        if matching:
            count=len(matching)
            message=(f'Ada {count} data bernama {name} dengan lokasi yang cocok, tetapi ID utama untuk lokasi ini belum ditentukan.'
                     if count>1 else f'Ada data bernama {name} dengan lokasi yang cocok, tetapi penetapan ID utamanya masih perlu dikonfirmasi.')
        else:
            message=f'Data bernama {name} ditemukan, tetapi hubungan wilayah untuk lokasi rekomendasi belum dapat dipastikan.'
        def order(record):
            # Display nearest evidence first without selecting or approving an ID.
            parent=self.records[level-1].get(record.get('Source_Parent_Id',''),{}) if level else {}
            pp=parent.get('_path') or ()
            return (pp!=path[:-1],pp[:1]!=path[:1],record['Source_Id'])
        shown=sorted(found,key=order)[:3]
        lines=[heading]
        if level:lines.append(f'• {LEVELS[level-1].capitalize()} yang diperlukan: '+ ' | '.join(path[:-1])+'.')
        lines.append('• '+message)
        for record in shown:
            detail=self.parent_location(record,level) if level else 'penetapan ID utama masih perlu dikonfirmasi'
            if level==3:
                city=self.records[1].get(record.get('Source_Direct_City_Id',''))
                if city:detail+='; kabupaten/kota langsung bernama '+city['Source_Name']
                else:detail+='; kabupaten/kota langsung kosong atau ID-nya tidak ditemukan di file'
            lines.append(f'• ID {record["Source_Id"]}: {detail}.')
        if len(found)>3:lines.append(f'• +{len(found)-3} data bernama sama lainnya; periksa lokasi masing-masing.')
        lines.append('Tindak lanjut: pastikan lokasi yang dimaksud dan periksa hubungan data di atas. ID dalam catatan hanya untuk pemeriksaan; belum ditetapkan sebagai ID tujuan.')
        return '\n'.join(lines)

    def source_conditions(self,source,path):
        level=len(path)-1
        if not level:return ''
        conditions=[]
        relations=[(level-1,path[:-1],source.get('Source_Parent_Id',''))]
        if level==3:relations.append((1,path[:2],source.get('Source_Direct_City_Id','')))
        for parent_level,parent_path,pid in relations:
            expected=self.targets[parent_level].get(parent_path,'')
            if expected and pid==expected:continue
            label='kabupaten/kota langsung' if level==3 and parent_level==1 else LEVELS[parent_level]
            if not pid:
                conditions.append(f'Kolom {label} utama saat ini kosong.')
                continue
            actual=self.records[parent_level].get(pid)
            if actual is None:
                conditions.append(f'ID {label} saat ini {pid} tidak ditemukan di file Salesforce yang diperiksa.')
            elif actual.get('Status')=='MAPPED_DUPLICATE' and actual.get('Target_Id')==expected and expected:
                conditions.append(f'{label.capitalize()} saat ini memakai data duplikat {actual["Source_Name"]} (ID {pid}); ID yang dipertahankan adalah {expected}.')
            else:
                pp=actual.get('_path')
                if pp and not actual.get('_blocked') and not actual.get('_requires_review'):
                    location=' | '.join(pp)
                else:location=actual['Source_Name']+'; lokasi lengkap dan hubungannya perlu dikonfirmasi'
                conditions.append(f'{label.capitalize()} utama saat ini: {location} (ID {pid}).')
        if not conditions:return ''
        return 'Kondisi data yang masih perlu diperiksa:\n'+'\n'.join('• '+s for s in conditions)

    def for_candidate(self,source,path,review):
        """Return presentation metadata only; do not mutate any mapping input."""
        pieces=[];selected=review['Candidate_Target_Id'] or review['Unverified_Master_ID']
        if not selected:pieces.append(self.missing_location_id(path))
        if selected==source['Source_Id'] and source['Source_Name']==path[-1]:
            current=self.source_conditions(source,path)
            if current:pieces.append(current)
        parents=[path[:-1]] if len(path)>1 else []
        if len(path)==4:parents.append(path[:2])
        for parent in parents:
            if not self.targets[len(parent)-1].get(parent):pieces.append(self.missing_location_id(parent))
        return {'Client_ID_Note':'\n\n'.join(pieces)}
