import csv,json,re,unicodedata,difflib,collections,pathlib,hashlib,zipfile,argparse
import openpyxl
import pandas as pd
from output_layout import csv_folder, write_guides
parser=argparse.ArgumentParser(description='Prepare hierarchy-aware Salesforce cleansing proposals; does not connect to Salesforce.')
parser.add_argument('--input-dir',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[2])
parser.add_argument('--output-dir',type=pathlib.Path)
args=parser.parse_args()
ROOT=args.input_dir;OUT=args.output_dir or ROOT/'cleansing'/'output';OUT.mkdir(parents=True,exist_ok=True)
wb=openpyxl.load_workbook(ROOT/'Service Territory MASTER FIX.xlsx',read_only=True,data_only=True)
s={sheet.title:[row for row in sheet.values if any(v is not None for v in row)] for sheet in wb}
wb.close()
levels=['Provinsi','KotaKabupaten','Kecamatan','Kelurahan']
kelurahan_file='Kelurahan.csv' if (ROOT/'Kelurahan.csv').exists() else 'Kelurahan with kecamatan Name.csv'
files=['Provinsi.csv','Kota Kabupaten.csv','Kecamatan.csv',kelurahan_file]
objects=['Provinsi__c','Kota_Kabupaten__c','Kecamatan__c','Kelurahan__c']
lookup=['','Provinsi__c','Kota_Kabupaten__c','Kecamatan__c']
data=[pd.read_csv(ROOT/f,dtype=str,keep_default_na=False,encoding='cp1252').to_dict('records') for f in files]
assert all(len(rows)==len({r['Id'] for r in rows}) for rows in data), 'Duplicate source IDs'
assert all(r.get('IsDeleted','').upper()=='FALSE' for rows in data for r in rows), 'Deleted or unknown-state source records require separate handling'
byid=[{r['Id']:r for r in rows} for rows in data]
paths=sorted(set((r[0],r[1],r[3],r[5]) for r in s['Service Territory'][1:]))
master=[set(p[:i+1] for p in paths) for i in range(4)]
def norm(x,i):
 x=unicodedata.normalize('NFKC',str(x or '')).casefold().strip()
 if i==1:
  x=re.sub(r'^kabupaten\b','kab',x);x=re.sub(r'^kota\s+administrasi\b','kota',x)
 if i==2:x=re.sub(r'^(kecamatan|kec)[.\s]+','',x)
 if i==3:x=re.sub(r'^(kelurahan|kel|desa)[.\s]+','',x)
 return re.sub(r'[^\w]+','',x)
indices=[]; children=[]; names=[]
for i in range(4):
 ix=collections.defaultdict(set);ch=collections.defaultdict(list);ns=collections.defaultdict(set)
 for p in sorted(master[i]):
  ix[(p[:-1],norm(p[-1],i))].add(p);ch[p[:-1]].append(p);ns[norm(p[-1],i)].add(p)
 indices.append(ix);children.append(ch);names.append(ns)
issues=[]; preferred=[collections.defaultdict(set) for _ in levels]
formula_maps=[]
for i in range(4):
 fm=collections.defaultdict(set)
 for p in master[i]:fm[''.join(p if i<2 else p[1:])].add(p)
 formula_maps.append(fm)
for i,(sheet,idcol) in enumerate([('Provinsi',1),('KotaKabupaten',2),('Kecamatan',2),('Kelurahan New',4)]):
 for row in s[sheet][1:]:
  key=row[0] if i==0 else row[2] if i==3 else row[1]
  ps=formula_maps[i].get(key,set())
  if len(ps)!=1:
   issues.append(dict(Object=objects[i],Issue='MASTER_SHEET_KEY_NOT_UNIQUE_OR_NOT_IN_SERVICE_TERRITORY',Key=key,Id=row[idcol] or ''));continue
  if row[idcol]:preferred[i][next(iter(ps))].add(str(row[idcol]))
results=[];maps=[];candidates=[];crosslevel=[]
def one(v):return next(iter(v)) if len(v)==1 else None
def match(i,name,parent):
 if parent is None:return None,'PARENT_UNRESOLVED'
 exact=parent+(name,)
 if exact in master[i]:return exact,'EXACT_HIERARCHY'
 vals=indices[i].get((parent,norm(name,i)),set())
 if len(vals)==1:return one(vals),'NORMALIZED_HIERARCHY'
 return None,'AMBIGUOUS_NORMALIZATION' if vals else 'NO_MATCH_IN_PARENT'
def suggestion(i,name,parent):
 pool=children[i].get(parent,[]) if parent is not None else list(names[i].get(norm(name,i),[]))
 scored=sorted(((round(100*difflib.SequenceMatcher(None,norm(name,i),norm(p[-1],i)).ratio(),2),p) for p in pool),key=lambda x:(-x[0],x[1]))
 return scored[:3]
for i,rows in enumerate(data):
 res=[];mapped={}
 for row in rows:
  rid=row['Id'];name=row['Name']; parent=() if i==0 else None; notes=[]; conflict=False; evidence=''; ancestor_review=False; direct_city=None
  if i>0:
   pid=row.get(lookup[i],'');pr=maps[i-1].get(pid)
   if pr and pr['_path'] and not pr['_blocked']:
    parent=pr['_path']; evidence='PARENT_LOOKUP_ID'; ancestor_review=pr.get('_requires_review',False)
   elif i==1:
    txt=row.get('Province Name','')
    parent=one(names[0].get(norm(txt,0),set()))
    if parent: evidence='PROVINCE_TEXT_RECOVERY';notes.append('Parent lookup missing or unresolved; province text used')
   elif i==2:
    txt=row.get('Kota Kabupaten Name','')
    parent=one(names[1].get(norm(txt,1),set()))
    if parent:evidence='UNIQUE_CITY_TEXT_RECOVERY';notes.append('Parent lookup missing or unresolved; unique city text used')
   if i==3:
    # Direct city lookup is independent evidence; never ignore a contradictory city.
    cr=maps[1].get(row.get('Kota_Kabupaten__c','')); city=cr['_path'] if cr and cr['_path'] and not cr['_blocked'] else None
    direct_city=city
    if parent and city and parent[:2]!=city:
     conflict=True;notes.append('Direct city lookup disagrees with city of linked kecamatan')
    if parent is None:
     legacy=row.get('Kecamatans__c',''); legacy_r=maps[2].get(legacy)
     if legacy_r and legacy_r['_path'] and not legacy_r['_blocked']:
      parent=legacy_r['_path'];evidence='LEGACY_KECAMATAN_ID_RECOVERY';notes.append('Recovered parent from legacy Kecamatans__c ID')
     else:
      txt=row.get('Kecamatan__r.Name','') or (legacy if not re.match(r'^[a-zA-Z0-9]{18}$',legacy) else '')
      if city:
       parent,_=match(2,txt,city)
       if parent:evidence='CITY_AND_DISTRICT_TEXT_RECOVERY';notes.append('Recovered parent from city lookup and district text')
     if parent and city and parent[:2]!=city:
      conflict=True;notes.append('Recovered kecamatan conflicts with direct city lookup')
   # Compare display columns only to raw lookup records; stale formulas are not overrides.
   textcol={1:'Province Name',2:'Kota Kabupaten Name',3:'Kecamatan__r.Name'}[i]
   if pid in byid[i-1] and row.get(textcol) and norm(row[textcol],i-1)!=norm(byid[i-1][pid]['Name'],i-1):
    notes.append('Exported parent display differs from lookup record name')
  path,method=match(i,name,parent)
  if i==1 and path is None and row.get('Name Changes','') and row['Name Changes']!=name:
   path,proposed_method=match(i,row['Name Changes'],parent)
   if path:method='USER_SUPPLIED_CITY_NAME_CHANGE';notes.append('Used supplied Name Changes column, validated within province')
  ref=row.get('Id Reference New' if i==3 else 'Id Referenced','')
  out={'Source_Id':rid,'Source_Name':name,'Source_Parent_Id':row.get(lookup[i],'') if i else '',
       'Source_Direct_City_Id':row.get('Kota_Kabupaten__c','') if i==3 else '',
       'Source_Direct_City_Resolved_Path':' | '.join(direct_city) if direct_city else '',
       'Source_Legacy_Kecamatans':row.get('Kecamatans__c',''),
       'Source_Postal_Code':row.get('Kode_Pos__c',''),
       'Supplied_Name_Changes':row.get('Name Changes',''),
       'Resolved_Parent_Path':' | '.join(parent) if parent else '',
       'Source_Parent_Display':row.get({1:'Province Name',2:'Kota Kabupaten Name',3:'Kecamatan__r.Name'}.get(i,''),''),
       'Gap_Analysis_Unmatched':'Yes' if not ref else 'No','Match_Method':method,'Parent_Evidence':evidence,
       'Target_Id':'','Target_Name':path[-1] if path else '',
       'Target_Provinsi':path[0] if path else '', 'Target_KotaKabupaten':path[1] if path and i>=1 else '',
       'Target_Kecamatan':path[2] if path and i>=2 else '', 'Target_Kelurahan':path[3] if path and i==3 else '',
       'Target_Parent_Id':'','Status':'','Action':'','Notes':'; '.join(notes),
       '_path':path,'_parent':parent,'_blocked':conflict,'_raw':row,
       '_requires_review':ancestor_review or bool(i and evidence!='PARENT_LOOKUP_ID')}
  if path is None or conflict:
   out['Status']='REVIEW_PARENT_CONFLICT' if conflict else 'REVIEW_UNMATCHED'
   out['Action']='REVIEW_ONLY'
   sugg=suggestion(i,name,parent)
   if conflict and direct_city and i==3:
    alternatives=[p for p in names[3].get(norm(name,3),set()) if p[:2]==direct_city]
    sugg=list(dict.fromkeys(sugg+[(100.0,p) for p in sorted(alternatives)]))
   for rank,(score,p) in enumerate(sugg,1):
    if score>=50:
     candidates.append({'Object':objects[i],'Source_Id':rid,'Source_Name':name,'Rank':rank,'Similarity':score,
                        'Candidate_Path':' | '.join(p),'Candidate_Name':p[-1],
                        'Reason':('Matches direct city evidence; conflicts with linked district' if conflict and direct_city and p[:2]==direct_city else 'Same linked or recovered parent' if parent is not None else 'Exact normalized name; parent unresolved'),
                        '_path':p,'_level':i})
  if (path is None or conflict) and i in (2,3):
   evidence_cities=set()
   if direct_city:evidence_cities.add(direct_city)
   if parent:evidence_cities.add(parent[:2])
   extra=[]
   for cp in sorted(names[3].get(norm(name,3),set())):
    if cp[:2] not in evidence_cities:continue
    if i==2:
     dest=cp[:3];reason='Source district name matches a master kelurahan in this city; confirm intended district'
     crosslevel.append({'Object':objects[i],'Source_Id':rid,'Source_Name':name,'Kelurahan_Master_Path':' | '.join(cp),'Candidate_Kecamatan_Path':' | '.join(dest),'Candidate_Kecamatan_Target_Id':'','_path':dest})
    else:
     dest=cp;reason='Exact kelurahan name within a city supported by source evidence; confirm district and conflicting city links'
    if dest not in [x[1] for x in extra]:extra.append((100.0,dest,reason))
   for rank,(score,cp,reason) in enumerate(extra,4):
    candidates.append({'Object':objects[i],'Source_Id':rid,'Source_Name':name,'Rank':rank,'Similarity':score,'Candidate_Path':' | '.join(cp),'Candidate_Name':cp[-1],'Reason':reason,'_path':cp,'_level':i})
  res.append(out);mapped[rid]=out
 results.append(res);maps.append(mapped)
 print('Mapped',levels[i],len(res),collections.Counter(r['Match_Method'] for r in res),flush=True)
# Verify preferred IDs against full hierarchy; select a unique exact-name source only if no preferred ID exists.
targets=[];master_rows=[]
for i in range(4):
 grouped=collections.defaultdict(list)
 for r in results[i]:
  if r['_path'] and not r['_blocked']:grouped[r['_path']].append(r)
 ts={}
 for p in sorted(master[i]):
  prefs=preferred[i].get(p,set()); valid=[rid for rid in prefs if rid in maps[i] and maps[i][rid]['_path']==p and not maps[i][rid]['_blocked'] and not maps[i][rid]['_requires_review']]
  chosen=valid[0] if len(prefs)==len(valid)==1 else ''
  state='VERIFIED_MASTER_ID' if chosen else ''
  if prefs and not chosen:
   state='REVIEW_MASTER_ID_CONFLICT'
   for rid in sorted(prefs):issues.append({'Object':objects[i],'Issue':'MASTER_TARGET_ID_DOES_NOT_VERIFY_AGAINST_FULL_HIERARCHY','Key':' | '.join(p),'Id':rid})
  if not prefs:
   exact=[r for r in grouped[p] if r['Source_Name']==p[-1] and not r['_requires_review']]
   if len(exact)==1:chosen=exact[0]['Source_Id'];state='UNIQUE_EXISTING_CANONICAL_NAME'
   elif len(exact)>1:state='REVIEW_MULTIPLE_CANONICAL_RECORDS'
   elif len(grouped[p])==1 and not grouped[p][0]['_requires_review']:
    chosen=grouped[p][0]['Source_Id'];state='UNIQUE_DETERMINISTIC_SOURCE_REQUIRES_RENAME'
   else:state='NO_CANONICAL_RECORD'
  ts[p]=chosen
  parentid=targets[i-1].get(p[:-1],'') if i else ''
  master_rows.append({'Object':objects[i],'Master_Path':' | '.join(p),'Name':p[-1],
     'Target_Id':chosen,'Parent_Target_Id':parentid,'Target_Resolution':state,
     'Deterministic_Source_Count':len(grouped[p]),'Master_Sheet_Id':';'.join(sorted(prefs)),
     'Provisioning_Action':('EXISTS' if chosen else 'REVIEW_TARGET_ID' if prefs or grouped[p] else 'INSERT_AFTER_PARENT_EXISTS'),
     '_path':p,'_level':i})
 targets.append(ts)
updates=[];repoints=[]
for i in range(4):
 for r in results[i]:
  p=r['_path']
  if not p:continue
  tid=targets[i].get(p,'');parid=targets[i-1].get(p[:-1],'') if i else ''
  r['Target_Id']=tid;r['Target_Parent_Id']=parid
  if r['_blocked']:continue
  if not tid:
   r['Status']='MAPPED_TARGET_UNRESOLVED';r['Action']='RESOLVE_OR_CREATE_CANONICAL_TARGET';continue
  if i and not parid:
   r['Status']='MAPPED_PARENT_TARGET_UNRESOLVED';r['Action']='RESOLVE_PARENT_TARGET';continue
  recovery=r['_requires_review']
  if recovery:
   r['Status']='REVIEW_RECOVERED_PARENT';r['Action']='REVIEW_RELATIONSHIP_RECOVERY';continue
  if tid!=r['Source_Id']:
   r['Status']='MAPPED_DUPLICATE';r['Action']='REPOINT_REFERENCES_THEN_RETIRE_AFTER_REVIEW'
   repoints.append({'Object':objects[i],'Source_Id':r['Source_Id'],'Target_Id':tid,'Source_Name':r['Source_Name'],
     'Target_Name':p[-1],'Master_Path':' | '.join(p),'Match_Method':r['Match_Method'],
     'Action':'Review dependencies; repoint references; retire duplicate only after validation'})
  else:
   change={}
   if r['Source_Name']!=p[-1]:change['Name']=p[-1]
   if i and r['Source_Parent_Id']!=parid:change[lookup[i]]=parid
   if i==3 and r['_raw'].get('Kota_Kabupaten__c','')!=targets[1].get(p[:2],''):
    if targets[1].get(p[:2],''):change['Kota_Kabupaten__c']=targets[1][p[:2]]
   r['Status']='CANONICAL_UPDATE_PROPOSED' if change else 'VALID_CANONICAL'
   r['Action']='UPDATE_AFTER_REVIEW' if change else 'KEEP'
   if change:updates.append({'Object':objects[i],'Id':tid,**change,'Original_Name':r['Source_Name'],'Original_Parent_Id':r['Source_Parent_Id'],'Original_Direct_City_Id':r['Source_Direct_City_Id'],'Master_Path':' | '.join(p)})
for c in candidates:c['Candidate_Target_Id']=targets[c['_level']].get(c['_path'],'')
for c in crosslevel:c['Candidate_Kecamatan_Target_Id']=targets[2].get(c['_path'],'')
def public(r):return {k:v for k,v in r.items() if not k.startswith('_')}
def write(name,rows,columns=None):
 rows=[public(r) for r in rows]
 keys=columns or list(dict.fromkeys(k for r in rows for k in r)) or ['No_records']
 dest=OUT/csv_folder(name)/name
 dest.parent.mkdir(parents=True,exist_ok=True)
 with dest.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(rows)
summary=[]
for i in range(4):
 rows=results[i];counts=collections.Counter(r['Status'] for r in rows)
 summary.append({'Object':objects[i],'Master_Count':len(master[i]),'Salesforce_Count':len(rows),
  'Gap_Analysis_Unmatched':sum(r['Gap_Analysis_Unmatched']=='Yes' for r in rows),
  **{k:counts[k] for k in ['VALID_CANONICAL','CANONICAL_UPDATE_PROPOSED','MAPPED_DUPLICATE','MAPPED_TARGET_UNRESOLVED','MAPPED_PARENT_TARGET_UNRESOLVED','REVIEW_RECOVERED_PARENT','REVIEW_PARENT_CONFLICT','REVIEW_UNMATCHED']}})
 write(f'{levels[i]}_all_records.csv',rows)
 write(f'{levels[i]}_cleansing_mapping.csv',[r for r in rows if r['Status']!='VALID_CANONICAL'],list(public(rows[0])))
 write(f'{levels[i]}_gap_invalid_mapping.csv',[r for r in rows if r['Gap_Analysis_Unmatched']=='Yes'],list(public(rows[0])))
 write(f'{levels[i]}_canonical_update_proposals.csv',[r for r in updates if r['Object']==objects[i]],list(dict.fromkeys(['Object','Id','Name']+([lookup[i]] if i else [])+(['Kota_Kabupaten__c'] if i==3 else [])+['Original_Name','Original_Parent_Id','Original_Direct_City_Id','Master_Path'])))
write('Cross_level_name_review.csv',crosslevel)
invalid_summary=[]
for i in range(4):
 inv=[r for r in results[i] if r['Gap_Analysis_Unmatched']=='Yes'];cc=collections.Counter(r['Status'] for r in inv)
 invalid_summary.append({'Object':objects[i],'Gap_Invalid_Count':len(inv),**dict(cc)})
write('Gap_invalid_summary.csv',invalid_summary)
write('Summary.csv',summary);write('Review_candidates.csv',candidates);write('Duplicate_repoint_proposals.csv',repoints)
write('Master_target_inventory.csv',master_rows)
write('Missing_or_unresolved_master_targets.csv',[r for r in master_rows if not r['Target_Id']])
write('Master_data_issues.csv',issues)
# Master duplicate rows / postal multiplicity are explicit.
postal=collections.defaultdict(set);cnt=collections.Counter()
for row in s['Service Territory'][1:]:
 p=(row[0],row[1],row[3],row[5]);postal[p].add(str(row[8] or ''));cnt[p]+=1
write('Master_duplicate_paths.csv',[{'Master_Path':' | '.join(p),'Rows':n,'Postal_Codes':';'.join(sorted(postal[p]))} for p,n in cnt.items() if n>1])
# Preserve and reconcile the user's original calculations.
recon=[]
for i,row in enumerate(s['SUMMARY'][1:5]):
 refs=sum(bool(r.get('Id Referenced','')) for r in data[i]);newrefs=sum(bool(r.get('Id Reference New','')) for r in data[i]) if i==3 else refs
 recon.append({'Object':objects[i],'Workbook_Master_Count':row[1],'Full_Hierarchy_Master_Count':len(master[i]),'Workbook_SF_Count':row[2],'CSV_SF_Count':len(data[i]),'Workbook_Unmatched':row[6], 'CSV_Legacy_Unmatched':len(data[i])-refs,'CSV_Full_Key_Unmatched':len(data[i])-newrefs})
write('Gap_analysis_reconciliation.csv',recon)
# Validate coverage and every deterministic match and proposed target.
for i,rs in enumerate(results):
 assert len(rs)==len(data[i]) and len({r['Source_Id'] for r in rs})==len(data[i])
 for r in rs:
  if r['_path']:assert r['_path'] in master[i]
  if r['Target_Id']:
   t=maps[i][r['Target_Id']];assert t['_path']==r['_path'] and not t['_blocked']
 for p,tid in targets[i].items():
  if tid:assert maps[i][tid]['_path']==p
assert all(r['Source_Id']!=r['Target_Id'] for r in repoints)
# Workbook review tables (no executable Salesforce import or deletion file).
with pd.ExcelWriter(OUT/'Salesforce_cleansing_review.xlsx',engine='xlsxwriter',engine_kwargs={'options':{'strings_to_formulas':False,'strings_to_urls':False}}) as writer:
 tabs={'Summary':summary,'Gap invalid summary':invalid_summary,'Cross level name review':crosslevel,'Gap reconciliation':recon,'Master issues':issues,'Master duplicate paths':[{'Master_Path':' | '.join(p),'Rows':n,'Postal_Codes':';'.join(sorted(postal[p]))} for p,n in cnt.items() if n>1],
       'Duplicate repoint proposals':repoints,'Review candidates':candidates,'Unresolved master targets':[r for r in master_rows if not r['Target_Id']]}
 for i in range(4):tabs[levels[i]+' mappings']=[r for r in results[i] if r['Status']!='VALID_CANONICAL']
 for name,rs in tabs.items():
  df=pd.DataFrame([public(r) for r in rs]);df.to_excel(writer,sheet_name=name,index=False)
  ws=writer.sheets[name];ws.freeze_panes(1,0)
  if len(df.columns):ws.autofilter(0,0,len(df),len(df.columns)-1);ws.set_column(0,len(df.columns)-1,24)
manifest=[]
for f in ROOT.glob('*'):
 if f.suffix in ['.csv','.xlsx'] and not f.name.startswith('~$'):manifest.append({'File':f.name,'Bytes':f.stat().st_size,'SHA256':hashlib.sha256(f.read_bytes()).hexdigest()})
write('Input_manifest.csv',manifest)
(OUT/'07_Audit').mkdir(exist_ok=True)
json.dump(summary,open(OUT/'07_Audit'/'summary.json','w'),indent=2)
write_guides(OUT)

print(json.dumps(summary,indent=2));print('issues',len(issues),'updates',len(updates),'repoints',len(repoints),'candidates',len(candidates),flush=True)
