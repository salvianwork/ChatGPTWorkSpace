# CSV usage guide

These folders are inside `Salesforce_cleansing_CSVs_and_scripts.zip`. Download and extract the ZIP to browse them.

The CSVs are grouped by purpose. The analysis snapshot is 29 October 2026; this folder reorganization does not change any mappings.

**Start with 00_Start_Here/Summary.csv.** No CSV is a pre-approved Salesforce upload. Review proposals and prepare object-specific upload files separately.

| Folder | CSV files | Purpose |
|---|---:|---|
| `00_Start_Here` | 1 | Overall counts. Start with Summary.csv; counts across other files overlap. |
| `01_Update_Proposals` | 4 | Proposed name/parent corrections. Review first; retain Id and only approved changed Salesforce fields in a separate upload file. Blank proposed fields mean no change. Do not upload audit columns. |
| `02_Duplicate_Handling` | 1 | Source-to-target duplicate mappings. Confirm and repoint all references before retiring any source record. This is not an upload or deletion list. |
| `03_Manual_Review` | 6 | Cleansing worklists, possible matches, and administrative-level questions. Resolve review statuses before applying a suggestion. Candidate rows can repeat a source record. |
| `04_Master_Targets` | 4 | Master inventory, unresolved Salesforce target IDs, and master-data issues. Unresolved targets are not all confirmed inserts; reconcile existing records and parents first. |
| `05_All_Records` | 4 | Complete reference exports with one mapping row per source record, including records that need no change. Reference only. |
| `06_Original_Gap_Analysis` | 6 | Records and counts from the original workbook gap analysis, plus reconciliation to the full hierarchy analysis. A subset/view of the other worklists. |
| `07_Audit` | 1 | Input checksums, validation results, and machine-readable summaries. Reference only; never upload these to Salesforce. |

## Recommended review order

1. Read the overall summary.
2. Review name/parent update proposals and duplicate references in province → city/regency → kecamatan → kelurahan order.
3. Resolve manual-review cases and master-target questions before using tentative IDs or creating new records.
4. Use full-record exports, gap-analysis comparisons, and audit files to verify decisions.

Rows repeat across views. Do not add file row counts together. Empty Provinsi worklists are intentional because all 38 provinces match.
