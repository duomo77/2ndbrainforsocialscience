# Retrieval and runtime diagnostics

## Network outcome

The local Python runtime had working internet access. **No DNS failure occurred.** Kolada v3 metadata and all nine KPI-year responses returned HTTP 200. SCB v2 schema, metadata, metropolitan codelist, selected data POST, XLS/PDF classification files, and the supplied TAB4824 bulk ZIP URL returned HTTP 200. The full ZIP is 24,492,021 bytes; it contains one 494,549,316-byte CSV. The CSV's encoding is Windows-1252, not UTF-8. All 29,376 selected counts agree exactly between bulk and API.

Every programmatic HTTP attempt is in `raw/requests.jsonl`, including UTC timestamp, method, requested/final URL, JSON body when present, response headers, elapsed time, bytes, SHA-256 and the exact Python exception when applicable. `results/source_manifest.csv` provides a readable index. Failed response bodies are retained, but never parsed as statistical observations. `raw/error_file_relocations.json` maps original error-body names to their `.http_error.txt` storage paths without rewriting the append-only request log.

## Supplemental document failures and recovery

These failures affected a reporting-change document, not the observed datasets:

1. `https://extra.skr.se/download/18.21af19d319762784ac14a0eb/1750176036743/F%C3%B6r%C3%A4ndringar%20i%20insamlingen%20av%20data%20till%20KKiK%202025.pdf`

   Exact Python exception: `HTTPError('404 Client Error:  for url: https://extra.skr.se/download/18.21af19d319762784ac14a0eb/1750176036743/F%C3%B6r%C3%A4ndringar%20i%20insamlingen%20av%20data%20till%20KKiK%202025.pdf')`.

2. The same `/download/...` path under `https://rka.nu/` also returned HTTP 404, logged with its full URL and error. An online page reader could read a cached copy of the original document, but that was not used as the only saved artifact.

3. Successful fallback: the document was downloaded with HTTP 200 from [Enköping municipality's official meeting archive](https://politik.enkoping.se/welcome-sv/namnder-styrelser/kommunfullmaktige/kommunfullmaktige-2025-11-04/agenda/forandringar-i-insamlingen-av-data-till-kkik-2025pdf?downloadMode=download). Its bytes start `%PDF-1.7`; saved as `raw/rka_kkik_changes_2025_municipal_mirror.pdf`. This RKA document explicitly retains U33401 for 2025 and discontinues U33402. It does not supply annual 2022–2025 questionnaires or certify invariant local reporting.

## Browser/page-reader export checks

The web page reader was also tried on official binary export links. Its exact limitations were:

- SCB bulk ZIP: `Failed to fetch https://www.statistikdatabasen.scb.se/Resources/PX/bulk/ssd/sv/TAB4824_sv.zip: (400) Unsupported content-type: application/x-zip-compressed`.
- SCB metropolitan XLS: `Failed to fetch https://www.scb.se/contentassets/c4b8142033a9440ca53725ca32321a74/storstadsomr.xls: (400) Unsupported content-type: application/vnd.ms-excel`.

These are page-reader content-type restrictions, not invalid export URLs or DNS failures. Both files were subsequently saved successfully by Python requests. No Google account or browser sign-in was necessary.

## Local processing corrections

No correction below replaced or imputed an observation:

- Initial console output encountered `UnicodeEncodeError: 'cp949' codec can't encode character '\xe4'`. Subsequent commands set `PYTHONIOENCODING=utf-8`; raw bytes were unaffected.
- Optional XLS inspection found `ImportError: Missing optional dependency 'xlrd'`. Membership was obtained directly from the official live SCB codelist with explicit value maps, checked against the 26/13/12 counts and Kolada names. The official XLS is retained unchanged.
- Attempting UTF-8 decoding of the bulk header produced `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe4 in position 13: invalid continuation byte`. Parsing correctly uses Windows-1252. Whole selected-data equality against SCB's UTF-8 JSON verifies the interpretation.
- First analysis report rendering encountered `ImportError: Missing optional dependency 'tabulate'`. A small plain Markdown formatter replaced that optional dependency. The full traceback is in `analysis_attempt1.log`.
- An initial metro-by-year formula generated redundant indicators, and the explicit design-rank assertion rejected it: `ValueError: full rank OLS_municipality_metro_by_year_FE/foreign_born_share`. The final code includes only non-reference metro × non-reference year indicators in addition to municipality/year effects. All final design matrices pass the rank assertion. Traceback: `analysis_attempt2.log`.
- A one-off terminal inspection command had a PowerShell/Python quoting `SyntaxError: unterminated string literal`; it was rerun using ordinary column filters. It did not alter any dataset or analysis file.

## Remaining source limitations

Year-specific 2022–2025 U33401 questionnaires and versioned KPI definitions were not authenticated. The current metadata, continued 2025 collection and actual reporting coverage are verified, but unchanged historical measurement is not established. TAB4824 has no 2025 child counts. No historical initial-placement dataset, origin-specific shift-share components, or defensible Z has been validated; first-stage and 2SLS estimates are therefore deliberately absent.
