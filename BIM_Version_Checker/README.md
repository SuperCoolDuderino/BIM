# BIM File Version Checker

Reports which Autodesk release year each Revit and Navisworks file was saved in, without opening Revit or Navisworks.

- **Revit:** `.rvt`, `.rfa`, `.rte`, `.rft`
- **Navisworks:** `.nwd`, `.nwc`, `.nwf`

Standard-library Python 3 only. There is nothing to `pip install`.

## Usage

1. Double-click `bim_version_checker.py`, or drag files or a folder onto it.
2. Choose **Select Folder** (scans subfolders too) or **Select Files**.
3. Choose where to save the report.

The report is saved as `DDMMYY_BIM_File_Version_Report.txt`:

```
File Version Report - 05/10/2026
==========================================

Project2.rvt = Revit 2026
Model_Dev.rvt = Revit 2024
Coordination.nwd = Navisworks 2025
```

## How it works

### Revit
Revit files are Microsoft Compound File Binary (OLE) containers, which work like a small file system inside one file. The release year is stored in an internal stream called `BasicFileInfo`:

```
Worksharing: Not enabled
Format: 2026
Build: 20260406_1515(x64)
```

The script includes a small compound-file reader that follows the container's allocation tables straight to that stream. It then reads `Format: YYYY` (Revit 2019 onwards), falling back to `Autodesk Revit YYYY` for older files. If the file can't be read as a compound file, it searches the whole file for the version text instead.

Two details matter here:
- `BasicFileInfo` can be stored **anywhere** in the file, not only near the start, so reading only the first part of the file is not enough.
- The text is UTF-16-LE and can start at an **odd** byte offset. The search patterns work on raw bytes, so they match at either alignment.

### Navisworks
`.nwd` and `.nwc` files are searched in full, in 4 MB chunks, for `Navisworks YYYY` as both ASCII and UTF-16 text. `.nwf` files are read as text (UTF-8 or UTF-16).

> **Not yet verified on real Navisworks files.** If a Navisworks file reports "version unknown", it may store its version in a compressed or binary form. Run the diagnostic script and report the result.

## Error messages in the report

| Report says | Meaning | Fix |
|---|---|---|
| `file not available offline …` | OneDrive or SharePoint has the file as online-only, so Windows can't read it | Right-click the file or folder, choose **Always keep on this device**, wait for the green tick, then re-run |
| `access denied …` | The file is locked or you don't have permission to read it | Check permissions, or close the file in any program that's locking it |
| `file not found …` | The file was moved or deleted during the scan | Re-run |
| `version unknown` | The file was read, but no version text was found | Run the diagnostic script |

## Diagnostics

`bim_version_diagnose.py` must be in the same folder as the checker. Drag a problem file onto it and it writes `bim_version_diagnose_report.txt`, which shows the step where reading failed:

1. **stat:** whether Windows can see the file, and whether OneDrive has it as online-only
2. **open/read:** whether Python can read the file at all
3. **compound-file parse:** the internal streams, and the version lines from `BasicFileInfo`
4. **checker result:** what the main checker reports for the file

The diagnostic report includes the file path, which may contain your Windows username. It does not include model content.
