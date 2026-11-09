"""Review-only context from actual legacy Parent IDs and bounded name forms."""
import re
from regional_matching import unique_identity_paths,name_identity_kind,normalize,REGION_MODIFIERS


def legacy_parent_context(raw,city,district_records,city_records,master_districts):
    """Return one district path for review; never fill the source's main FK."""
    if not city or raw.get('Kecamatan__c') not in (None,'','0'):return None
    legacy=raw.get('Kecamatans__c','');linked=district_records.get(legacy)
    if linked:
        if linked.get('_blocked'):return None
        actual_city=city_records.get(linked.get('Source_Parent_Id',''))
        if not actual_city or actual_city.get('_blocked') or actual_city.get('_requires_review') or actual_city.get('_path')!=city:return None
        name=linked['Source_Name']
    else:
        if re.fullmatch(r'[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?',legacy or ''):return None
        name=raw.get('Kecamatan__r.Name') or legacy
    if not name:return None
    hits=unique_identity_paths(2,name,city,master_districts)
    if len(hits)!=1:return None
    path=next(iter(hits))
    return path,(f'Parent untuk review diambil dari relasi lama “{name}”, dicocokkan dengan '
                 f'{" | ".join(path)} pada master dan kabupaten/kota yang tercatat. '
                 'Kolom kecamatan utama masih kosong; pengisian atau penggabungan menunggu konfirmasi Tim Daikin.')


def city_alias_candidates(name,city,paths):
    """Alias evidence within a known city, without claiming its district is known."""
    if not city:return []
    return [(p,'Nama inti/alias pada master cocok dalam kabupaten/kota yang tercatat; '
             'kecamatan sumber belum diketahui dan perlu dikonfirmasi.')
            for p in sorted(paths) if p[:2]==city and name_identity_kind(name,p[-1],3,p[:-1])]


def one_edit_typo(source,target,level):
    if level not in (2,3):return False
    words=lambda x:(set(re.findall(r'\w+',x.casefold()))&REGION_MODIFIERS)|{m for m in REGION_MODIFIERS if normalize(x,level).startswith(m) or normalize(x,level).endswith(m)}
    numbers=lambda x:re.findall(r'\d+|\b[ivxlcdm]+\b',x.casefold())
    if words(source)!=words(target) or numbers(source)!=numbers(target):return False
    a,b=normalize(source,level),normalize(target,level)
    if min(len(a),len(b))<8 or a==b or abs(len(a)-len(b))>1:return False
    if len(a)==len(b):return sum(x!=y for x,y in zip(a,b))==1
    short,long=(a,b) if len(a)<len(b) else (b,a)
    if long[-1] in 'ivx' and long[:-1]==short:return False
    return any(long[:i]+long[i+1:]==short for i in range(len(long)))
