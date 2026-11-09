"""Master paths actually used by cross-level recommendations; no inferred IDs."""
import re

LEVELS=['Provinsi','Kota/Kabupaten','Kecamatan','Kelurahan']


def candidate_proof(record):
    """Extract a bounded, full master path already used to recommend its parent."""
    reason=record.get('Reason',record.get('Alasan',''))
    match=re.match(r'^Nama sumber ditemukan sebagai (Provinsi|Kota/Kabupaten|Kecamatan|Kelurahan): (.*?)\. Jika record',reason)
    if not match:return None
    label,path=match.groups();parts=tuple(path.split(' | '))
    if len(parts)!=LEVELS.index(label)+1:return None
    candidate=record.get('Candidate_Path',record.get('Hierarki_Kandidat',''))
    target=tuple(candidate.split(' | '))
    if not candidate or len(target)>=len(parts) or parts[:len(target)]!=target:return None
    return parts


def rename_recommendation_label(value):
    if not isinstance(value,str):return value
    return re.sub(r'\b([Rr]ekomendasi) 1\b',r'\1',value)
