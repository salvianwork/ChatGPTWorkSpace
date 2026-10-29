# Salesforce service territory cleansing review

Prepared from the workbook and four CSV exports in this repository on 29 October 2026. This is a mapping and review package. No Salesforce records have been changed.

## Start here

Open `output/Salesforce_cleansing_review.xlsx`. The workbook contains the summary, invalid-record counts, object mappings, duplicate repoint proposals, review candidates, cross-level name cases, unresolved master targets, and master-data issues. For all source rows, including unchanged valid records, use the four `*_all_records.csv` files.

| Object | Export records | Keep | Canonical updates proposed | Duplicate repoints proposed | Review / unresolved |
|---|---:|---:|---:|---:|---:|
| Provinsi__c | 38 | 38 | 0 | 0 | 0 |
| Kota_Kabupaten__c | 890 | 54 | 458 | 311 | 67 |
| Kecamatan__c | 7,828 | 6,081 | 608 | 158 | 981 |
| Kelurahan__c | 82,550 | 46,246 | 7,529 | 2,636 | 26,139 |

The 8,595 update proposals affect canonical records. The 3,105 repoint proposals identify other records representing the same location as a verified target; they are not a deletion list. Both require business review and Salesforce dependency checks before execution.

## Download layout

The review branch contains the standalone Excel workbook and `Salesforce_cleansing_CSVs_and_scripts.zip`. The ZIP contains all CSV mappings, the audit reports, and reproducible script; download the workbook separately. Extract the ZIP to recover the individual CSV files.

## Matching rules

1. Use distinct tuple keys from `Service Territory`: province; province + city; province + city + kecamatan; province + city + kecamatan + kelurahan. Display paths use ` | ` separators for readability, not as a concatenated matching key.
2. Resolve parent lookups through the exported IDs. Use your city `Name Changes` values only when they validate within the resolved province. Normalize case, spacing, punctuation, and explicit administrative prefixes only where the normalized result is unique within the parent.
3. Use missing-parent text and legacy `Kecamatans__c` only as recovery evidence, retaining review status. Parent recovery is never sufficient for a canonical update or duplicate retirement proposal. Recovery inherited from a parent also requires review.
4. When a kelurahan direct city lookup disagrees with the linked kecamatan city, keep it in `REVIEW_PARENT_CONFLICT`. The direct city and linked parent path are both recorded. Neither relationship is silently overwritten.
5. Verify preferred workbook target IDs against the complete exported hierarchy. Do not trust a workbook lookup ID alone. When the workbook has no target ID, a unique existing canonical-name record, or a single deterministic source requiring renaming, may supply a target. Conflicting preferred IDs are held for review.
6. Similarity candidates and same-city name candidates are suggestions only. Similarity is a character-comparison score, not a probability or confidence percentage. No fuzzy suggestion is promoted to an approved mapping.

## Important findings

- All 38 provinces match the master.
- `Service Territory` has 83,763 rows but 83,759 distinct complete kelurahan paths. Four paths have duplicate rows, potentially with different postal codes. `Kelurahan New` is consistent with the 83,759 full paths. The older `Kelurahan` sheet has 83,579 entries and uses kecamatan + kelurahan, which is not sufficient to disambiguate all locations.
- The older Summary reports 19,727 unmatched kelurahan; the newer full city + kecamatan + kelurahan key flags 24,340. Both source calculations are preserved in `Gap_analysis_reconciliation.csv`.
- 11,181 exported kelurahan have conflicting direct-city and kecamatan-city relationships. This includes some rows the original name-only gap analysis considered matched.
- 441 unmatched kecamatan source records have names also found as kelurahan within the same city. The separate cross-level table suggests the actual parent kecamatan for review; it does not assume these records should be merged.
- 4,460 preferred kelurahan master IDs cannot be verified without reviewing missing or conflicting parent relationships. See `Master_data_issues.csv`. This is a validation concern, not proof that every listed workbook ID is incorrect.

## Files

- `*_gap_invalid_mapping.csv`: only records your original analysis flagged as unmatched (using `Id Reference New` for kelurahan).
- `*_cleansing_mapping.csv`: all records needing action or review, including newly detected hierarchy problems.
- `*_all_records.csv`: one output row per source record with IDs, proposed master hierarchy, match method, status, action, and notes.
- `*_canonical_update_proposals.csv`: proposed changed fields plus original names and parent IDs for audit. Blank proposed fields mean no change; do not use blanks to clear Salesforce fields. These tables include audit columns and are not direct Data Loader import files.
- `Duplicate_repoint_proposals.csv`: source-to-target IDs for deterministic duplicates.
- `Review_candidates.csv`: alternatives for uncertain names, parent conflicts, and possible administrative-level errors. Some sources have no justified candidate and remain unmatched. Candidate target IDs may be blank until a canonical record is resolved or created.
- `Master_target_inventory.csv` and `Missing_or_unresolved_master_targets.csv`: every master location and its target-resolution state. Insert suggestions are provisional; reconcile unresolved source records first to avoid creating more duplicates.
- `Input_manifest.csv` and `Validation_report.json`: input checksums and data-integrity validation.

For every `REVIEW_*` row, populated target fields are tentative evidence only. Resolve the review status before using any suggested ID. `MAPPED_TARGET_UNRESOLVED` rows have a matching master path but no safely verified target ID; they are not approved repoints.

## Review and apply

Review in province → city/regency → kecamatan → kelurahan order. Confirm uncertain parent links and master target IDs first. For approved updates, create object-specific Data Loader files containing `Id` and only the approved changed Salesforce fields. Apply small batches in a sandbox, verify counts and relationships, then use the same approved process in production.

These are custom objects: do not assume Salesforce supports the standard Account/Contact merge operation for them. Before retiring a duplicate, inventory and repoint all referencing lookups across the org, not only those in these four exports. The package contains no executable deletion list. Postal codes are retained as source evidence and are not automatically changed.

## Reproduce

Requires Python 3.12 and the versions in `requirements.txt`:

```bash
python cleansing/scripts/cleanse.py --input-dir . --output-dir cleansing/output
```

The script reads the local workbook and CSVs only. It does not authenticate to Salesforce, modify inputs, or make network calls. The script accepts either `Kelurahan.csv` or the earlier `Kelurahan with kecamatan Name.csv`; GitHub renamed this input without changing its content. The manifest retains the filename of the analyzed snapshot. The input files are decoded as Windows-1252 because the exports contain bytes that are not valid UTF-8. Output CSVs use UTF-8 with BOM. Open CSV IDs as text in spreadsheet tools.

The generator asserts input coverage, unique IDs, full-hierarchy target membership, and non-self duplicate mappings. The accompanying validation report also verifies parent-target consistency, absence of repoint cycles, exclusion of review cases from update proposals, and formula-free workbook output.
