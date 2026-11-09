"""Explicit four-level export text supplies review evidence only, never a mapping."""
import re
from collections import defaultdict
from regional_matching import normalize,city_parts,province_name_forms,identity_forms,name_identity_kind

TEXT_REASON='Teks lokasi ekspor cocok dengan struktur master: '


class LocationTextIndex:
    def __init__(self,paths):
        self.names=defaultdict(set)
        for p in paths:
            for form in identity_forms(p[-1],3,p[:-1]):self.names[form].add(p)

    def candidates(self,name,raw):
        text=raw.get('Combined__c','').strip()
        parts=[p.strip() for p in text.split(',')]
        if len(parts)==5 and re.fullmatch(r'\d{5}',parts[-1]):parts[-2]+=' '+parts.pop()
        if len(parts)!=4 or not all(parts) or normalize(parts[0],3)!=normalize(name,3):return []
        province=parts[3];code=re.search(r'\s+(\d{5})$',province)
        if code:
            supplied=raw.get('Kode_Pos__c','').strip()
            if supplied not in ('','0') and supplied!=code[1]:return []
            province=province[:code.start()].strip()
        kind,core=city_parts(parts[2]);found=[]
        for p in sorted(self.names.get(normalize(name,3),())):
            pk,pc=city_parts(p[1])
            if normalize(province,0) not in province_name_forms(p[0]):continue
            if not core or core!=pc or (kind and kind!=pk):continue
            if not name_identity_kind(parts[1],p[2],2,p[:2]):continue
            found.append(p)
        # Do not silently choose a city/kabupaten or alias if text is ambiguous.
        if len(found)!=1:return []
        p=found[0]
        reason=(TEXT_REASON+' | '.join(p)+'. '
                'Teks pada ekspor: “'+text+'”. Nama, kecamatan, kabupaten/kota, dan provinsi cocok dengan master. '
                'Konfirmasikan lokasi dan relasi Parent yang bertentangan atau belum sesuai; ID final tidak ditetapkan otomatis.')
        return [(p,reason)]
