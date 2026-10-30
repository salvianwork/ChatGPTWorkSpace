from pathlib import Path
import csv
FOLDERS={
 '00_Start_Here':'Overall counts. Start with Summary.csv; counts across other files overlap.',
 '01_Update_Proposals':'Proposed name/parent corrections. Review first; retain Id and only approved changed Salesforce fields in a separate upload file. Blank proposed fields mean no change. Do not upload audit columns.',
 '02_Duplicate_Handling':'Source-to-target duplicate mappings. Confirm and repoint all references before retiring any source record. This is not an upload or deletion list.',
 '03_Manual_Review':'Cleansing worklists, possible matches, and administrative-level questions. Resolve review statuses before applying a suggestion. Candidate rows can repeat a source record.',
 '04_Master_Targets':'Master inventory, unresolved Salesforce target IDs, and master-data issues. Unresolved targets are not all confirmed inserts; reconcile existing records and parents first.',
 '05_All_Records':'Complete reference exports with one mapping row per source record, including records that need no change. Reference only.',
 '06_Original_Gap_Analysis':'Records and counts from the original workbook gap analysis, plus reconciliation to the full hierarchy analysis. A subset/view of the other worklists.',
 '07_Audit':'Input checksums, validation results, and machine-readable summaries. Reference only; never upload these to Salesforce.'}
def csv_folder(name):
 if name=='Summary.csv':return '00_Start_Here'
 if name.endswith('_canonical_update_proposals.csv'):return '01_Update_Proposals'
 if name=='Duplicate_repoint_proposals.csv':return '02_Duplicate_Handling'
 if name.endswith('_cleansing_mapping.csv') or name in ('Review_candidates.csv','Cross_level_name_review.csv'):return '03_Manual_Review'
 if name in ('Master_target_inventory.csv','Missing_or_unresolved_master_targets.csv','Master_data_issues.csv','Master_duplicate_paths.csv'):return '04_Master_Targets'
 if name.endswith('_all_records.csv'):return '05_All_Records'
 if name.endswith('_gap_invalid_mapping.csv') or name in ('Gap_invalid_summary.csv','Gap_analysis_reconciliation.csv'):return '06_Original_Gap_Analysis'
 if name=='Input_manifest.csv':return '07_Audit'
 raise ValueError('Unclassified CSV: '+name)
def write_guides(root):
 root=Path(root);lines=['# CSV usage guide','','The CSVs are grouped by purpose. The analysis snapshot is 29 October 2026; this folder reorganization does not change any mappings.','','**Start with 00_Start_Here/Summary.csv.** No CSV is a pre-approved Salesforce upload. Review proposals and prepare object-specific upload files separately.','','| Folder | CSV files | Purpose |','|---|---:|---|']
 for folder,purpose in FOLDERS.items():
  d=root/folder;d.mkdir(parents=True,exist_ok=True);files=sorted(d.glob('*.csv'))
  rows=[]
  for p in files:
   with p.open(encoding='utf-8-sig',newline='') as f:
    reader=csv.reader(f);next(reader,None);n=sum(1 for _ in reader)
   rows.append((p.name,n))
  table=['| CSV | Data rows |','|---|---:|']+[f'| [{name}]({name}) | {n:,} |' for name,n in rows]
  (d/'README.md').write_text('# '+folder.replace('_',' ')+'\n\n'+purpose+'\n\n'+'\n'.join(table)+'\n',encoding='utf-8')
  lines.append(f'| [{folder}]({folder}/README.md) | {len(files)} | {purpose} |')
 lines+=['','## Recommended review order','','1. Read the overall summary.','2. Review name/parent update proposals and duplicate references in province → city/regency → kecamatan → kelurahan order.','3. Resolve manual-review cases and master-target questions before using tentative IDs or creating new records.','4. Use full-record exports, gap-analysis comparisons, and audit files to verify decisions.','','Rows repeat across views. Do not add file row counts together. Empty Provinsi worklists are intentional because all 38 provinces match.','']
 (root/'README.md').write_text('\n'.join(lines),encoding='utf-8')
