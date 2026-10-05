#!/usr/bin/env python3
"""
BIM File Version Checker
Detects Revit and Navisworks file versions from binary file content.
Usage: Double-click to run, or drag a folder / files onto this script.

No third-party packages required - standard library only.
"""

import sys
import os
import errno
import re
import struct
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox

REVIT_EXTENSIONS     = {'.rvt', '.rfa', '.rte', '.rft'}
NAVISWORKS_EXTENSIONS = {'.nwd', '.nwc', '.nwf'}


# ---------------------------------------------------------------------------
# Folder / file browsing
# ---------------------------------------------------------------------------

def _make_root():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    return root

def browse_scan_target():
    """Ask the user whether to pick a folder or individual files."""
    choice = {'value': None}

    root = _make_root()
    root.deiconify()
    root.title("BIM Version Checker")
    root.resizable(False, False)

    tk.Label(root, text="What would you like to scan?",
             font=("Arial", 11), pady=12, padx=20).pack()

    btn_frame = tk.Frame(root, pady=10, padx=20)
    btn_frame.pack()

    def pick_folder():
        root.withdraw()
        folder = filedialog.askdirectory(title="Select Folder to Scan")
        root.destroy()
        if folder:
            choice['value'] = [folder]

    def pick_files():
        root.withdraw()
        files = filedialog.askopenfilenames(
            title="Select Files",
            filetypes=[
                ("BIM Files", "*.rvt *.rfa *.rte *.rft *.nwd *.nwc *.nwf"),
                ("Revit Files", "*.rvt *.rfa *.rte *.rft"),
                ("Navisworks Files", "*.nwd *.nwc *.nwf"),
                ("All Files", "*.*"),
            ]
        )
        root.destroy()
        if files:
            choice['value'] = list(files)

    tk.Button(btn_frame, text="  Select Folder  ", width=16,
              command=pick_folder).grid(row=0, column=0, padx=8)
    tk.Button(btn_frame, text="  Select Files   ", width=16,
              command=pick_files).grid(row=0, column=1, padx=8)

    root.mainloop()
    return choice['value'] or None

def browse_output_folder():
    root = _make_root()
    folder = filedialog.askdirectory(title="Select Output Folder for Report")
    root.destroy()
    return folder or None


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def collect_files(paths):
    """Accept a list of file/folder paths; return sorted Revit + NW lists."""
    revit, navis = [], []
    for path in paths:
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for name in files:
                    fp = os.path.join(root, name)
                    ext = os.path.splitext(name)[1].lower()
                    if ext in REVIT_EXTENSIONS:
                        revit.append(fp)
                    elif ext in NAVISWORKS_EXTENSIONS:
                        navis.append(fp)
        elif os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in REVIT_EXTENSIONS:
                revit.append(path)
            elif ext in NAVISWORKS_EXTENSIONS:
                navis.append(path)
    return sorted(revit), sorted(navis)


# ---------------------------------------------------------------------------
# Minimal compound-file (OLE / CFB) reader
#
# Revit files (.rvt/.rfa/.rte/.rft) are Microsoft Compound File Binary
# containers - a mini file system inside one file. The version text lives in
# a small internal stream called "BasicFileInfo", which can sit anywhere in
# the file (not necessarily near the start), so we follow the container's
# allocation tables to read that stream directly.
# ---------------------------------------------------------------------------

CFB_SIGNATURE = b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'
_ENDOFCHAIN   = 0xFFFFFFFE
_FREESECT     = 0xFFFFFFFF
_MAX_REGULAR  = 0xFFFFFFFA   # sector ids >= this are special markers


class CompoundFileError(Exception):
    pass


class CompoundFile:
    """Read-only access to streams inside a compound file (standard library only)."""

    def __init__(self, f):
        self.f = f
        f.seek(0, os.SEEK_END)
        self.file_size = f.tell()
        f.seek(0)
        header = f.read(512)
        if len(header) < 512 or header[:8] != CFB_SIGNATURE:
            raise CompoundFileError("not a compound file")

        self.sector_size      = 1 << struct.unpack_from('<H', header, 0x1E)[0]
        self.mini_sector_size = 1 << struct.unpack_from('<H', header, 0x20)[0]
        num_fat_sectors       = struct.unpack_from('<I', header, 0x2C)[0]
        first_dir_sector      = struct.unpack_from('<I', header, 0x30)[0]
        self.mini_cutoff      = struct.unpack_from('<I', header, 0x38)[0]
        first_minifat_sector  = struct.unpack_from('<I', header, 0x3C)[0]
        first_difat_sector    = struct.unpack_from('<I', header, 0x44)[0]
        num_difat_sectors     = struct.unpack_from('<I', header, 0x48)[0]

        if self.sector_size not in (512, 4096):
            raise CompoundFileError("unsupported sector size")
        self.max_sectors = self.file_size // self.sector_size + 1

        # --- Build the FAT (sector allocation table) via the DIFAT ---------
        fat_sector_ids = [s for s in struct.unpack_from('<109I', header, 0x4C)
                          if s < _MAX_REGULAR]
        ids_per_sector = self.sector_size // 4
        difat_sector = first_difat_sector
        for _ in range(num_difat_sectors):
            if difat_sector >= _MAX_REGULAR:
                break
            entries = struct.unpack('<%dI' % ids_per_sector,
                                    self._read_sector(difat_sector))
            fat_sector_ids.extend(s for s in entries[:-1] if s < _MAX_REGULAR)
            difat_sector = entries[-1]
        fat_sector_ids = fat_sector_ids[:num_fat_sectors]

        fat_bytes = b''.join(self._read_sector(s) for s in fat_sector_ids)
        self.fat = struct.unpack('<%dI' % (len(fat_bytes) // 4), fat_bytes)

        # --- Directory entries ---------------------------------------------
        dir_bytes = self._read_chain(first_dir_sector)
        self.entries = []
        for off in range(0, len(dir_bytes) - 127, 128):
            name_len   = struct.unpack_from('<H', dir_bytes, off + 64)[0]
            entry_type = dir_bytes[off + 66]
            start      = struct.unpack_from('<I', dir_bytes, off + 116)[0]
            size       = struct.unpack_from('<Q', dir_bytes, off + 120)[0]
            if self.sector_size == 512:
                size &= 0xFFFFFFFF   # v3 files: high dword may contain junk
            name_len = min(max(name_len - 2, 0), 62)   # strip terminating null
            name = dir_bytes[off:off + name_len].decode('utf-16-le', errors='replace')
            self.entries.append((name, entry_type, start, size))

        if not self.entries or self.entries[0][1] != 5:
            raise CompoundFileError("missing root entry")

        # --- Mini stream + mini FAT (where small streams live) -------------
        _, _, root_start, root_size = self.entries[0]
        self._mini_stream = None
        self._mini_stream_start, self._mini_stream_size = root_start, root_size
        minifat_bytes = (self._read_chain(first_minifat_sector)
                         if first_minifat_sector < _MAX_REGULAR else b'')
        self.minifat = struct.unpack('<%dI' % (len(minifat_bytes) // 4), minifat_bytes)

    def _read_sector(self, sector_id):
        self.f.seek((sector_id + 1) * self.sector_size)
        return self.f.read(self.sector_size)

    def _read_chain(self, start, size=None):
        parts, sector, count = [], start, 0
        while sector < _MAX_REGULAR:
            if sector >= len(self.fat) or count > self.max_sectors:
                raise CompoundFileError("corrupt sector chain")
            parts.append(self._read_sector(sector))
            sector = self.fat[sector]
            count += 1
            if size is not None and count * self.sector_size >= size:
                break
        data = b''.join(parts)
        return data[:size] if size is not None else data

    def _read_mini_chain(self, start, size):
        if self._mini_stream is None:
            self._mini_stream = self._read_chain(self._mini_stream_start,
                                                 self._mini_stream_size)
        parts, sector, count = [], start, 0
        max_mini = len(self.minifat)
        while sector < _MAX_REGULAR:
            if sector >= max_mini or count > max_mini:
                raise CompoundFileError("corrupt mini sector chain")
            off = sector * self.mini_sector_size
            parts.append(self._mini_stream[off:off + self.mini_sector_size])
            sector = self.minifat[sector]
            count += 1
            if count * self.mini_sector_size >= size:
                break
        return b''.join(parts)[:size]

    def stream_names(self):
        return [e[0] for e in self.entries if e[1] == 2]

    def read_stream(self, name):
        """Return the bytes of the first stream called `name`, or None."""
        for entry_name, entry_type, start, size in self.entries:
            if entry_type == 2 and entry_name == name:
                if size < self.mini_cutoff:
                    return self._read_mini_chain(start, size)
                return self._read_chain(start, size)
        return None


# ---------------------------------------------------------------------------
# Version text search
#
# Text inside Revit/Navisworks files may be stored as plain single-byte text
# or as UTF-16-LE (two bytes per character, e.g. "R\x00e\x00v\x00..."), and a
# UTF-16 string may start at an odd OR even byte offset. Searching the raw
# bytes with patterns built for both encodings handles all of these cases.
# ---------------------------------------------------------------------------

def _label_patterns(label, max_gap=25):
    """Compiled byte patterns finding '<label> ... YYYY' in ASCII and UTF-16-LE."""
    ascii_label = re.escape(label.encode('ascii'))
    utf16_label = re.escape(label.encode('utf-16-le'))
    ascii_pat = re.compile(
        ascii_label + rb'[^0-9]{0,%d}?(20[0-9]{2})(?![0-9])' % max_gap,
        re.DOTALL)
    utf16_pat = re.compile(
        utf16_label + rb'(?:(?![0-9]\x00)..){0,%d}?' % max_gap
        + rb'(2\x000\x00[0-9]\x00[0-9]\x00)(?![0-9]\x00)',
        re.DOTALL)
    return utf16_pat, ascii_pat


def _decode_year(raw):
    return raw.replace(b'\x00', b'').decode('ascii')


def _search_year(data, patterns, at_eof=True):
    """Return the first year found in `data` by any of `patterns`, else None.

    When `data` is one chunk of a larger file (at_eof=False), matches touching
    the end of the chunk are ignored - the overlap with the next chunk will
    re-check them with full context.
    """
    for pat in patterns:
        for m in pat.finditer(data):
            if not at_eof and m.end() >= len(data) - 2:
                continue
            return _decode_year(m.group(1))
    return None


_REVIT_FORMAT_PATTERNS   = _label_patterns('Format:', max_gap=5)
_REVIT_PRODUCT_PATTERNS  = _label_patterns('Autodesk Revit')
_REVIT_GENERIC_PATTERNS  = _label_patterns('Revit')
_NAVIS_PATTERNS          = _label_patterns('Navisworks')

_CHUNK_SIZE = 4 * 1024 * 1024    # 4 MB per read when scanning a whole file
_OVERLAP    = 512                # bytes re-checked across chunk boundaries


def _scan_whole_file(filepath, patterns):
    """Search an entire file in chunks; return the first year found or None."""
    tail = b''
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(_CHUNK_SIZE)
            at_eof = len(chunk) < _CHUNK_SIZE
            data = tail + chunk
            year = _search_year(data, patterns, at_eof=at_eof)
            if year or at_eof:
                return year
            tail = data[-_OVERLAP:]


# ---------------------------------------------------------------------------
# Version detection
# ---------------------------------------------------------------------------

# Windows file attributes set on OneDrive / SharePoint "online-only" files
_FILE_ATTRIBUTE_OFFLINE               = 0x00001000
_FILE_ATTRIBUTE_RECALL_ON_OPEN        = 0x00040000
_FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000
_CLOUD_ATTRIBUTES = (_FILE_ATTRIBUTE_OFFLINE | _FILE_ATTRIBUTE_RECALL_ON_OPEN
                     | _FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)


def _is_cloud_only(filepath):
    """True if Windows marks the file as an online-only cloud placeholder."""
    try:
        attrs = getattr(os.stat(filepath), 'st_file_attributes', 0)
    except OSError:
        return False
    return bool(attrs & _CLOUD_ATTRIBUTES)


def _read_error(product, filepath, e):
    """Plain-English report text for a file that could not be read."""
    winerror = getattr(e, 'winerror', None)
    cloud_error = winerror is not None and 358 <= winerror <= 400   # ERROR_CLOUD_FILE_*
    if cloud_error or e.errno == errno.EINVAL or _is_cloud_only(filepath):
        reason = ("file not available offline - in OneDrive/SharePoint right-click "
                  "it and choose 'Always keep on this device', then re-run")
    elif isinstance(e, PermissionError):
        reason = "access denied - the file may be locked or you lack permission"
    elif isinstance(e, FileNotFoundError):
        reason = "file not found - it may have been moved or deleted"
    else:
        reason = f"could not read file: {e.strerror or e.__class__.__name__}"
    return f"{product} ({reason})"

def _revit_year_from_basic_file_info(filepath):
    """Read Revit's BasicFileInfo stream and pull out the release year."""
    with open(filepath, 'rb') as f:
        cfb = CompoundFile(f)
        info = cfb.read_stream('BasicFileInfo')
    if not info:
        return None
    # 'Format: 2024' (Revit 2019+) is the most reliable marker; older files
    # only carry e.g. 'Autodesk Revit 2018 (Build: ...)'.
    for patterns in (_REVIT_FORMAT_PATTERNS, _REVIT_PRODUCT_PATTERNS,
                     _REVIT_GENERIC_PATTERNS):
        year = _search_year(info, patterns)
        if year:
            return year
    return None


def get_revit_version(filepath):
    # 1) Preferred: read the BasicFileInfo stream directly.
    try:
        year = _revit_year_from_basic_file_info(filepath)
        if year:
            return f"Revit {year}"
    except CompoundFileError:
        pass            # not a valid compound file - try the fallback scan
    except OSError as e:
        return _read_error('Revit', filepath, e)
    except Exception:
        pass

    # 2) Fallback: scan the whole file for 'Revit YYYY'.
    try:
        year = _scan_whole_file(
            filepath, _REVIT_PRODUCT_PATTERNS + _REVIT_GENERIC_PATTERNS)
        if year:
            return f"Revit {year}"
    except OSError as e:
        return _read_error('Revit', filepath, e)
    return "Revit (version unknown)"


def get_navisworks_version(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    try:
        # NWF files can be plain text / XML (UTF-8 or UTF-16)
        if ext == '.nwf':
            with open(filepath, 'rb') as f:
                raw = f.read()
            if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
                content = raw.decode('utf-16', errors='replace')
            else:
                content = raw.decode('utf-8', errors='replace')
            m = re.search(r'Navisworks[^0-9]{0,25}?(20\d{2})(?!\d)',
                          content, re.IGNORECASE)
            if m:
                return f"Navisworks {m.group(1)}"

        # NWD / NWC (and NWF fallback) - scan the whole file
        year = _scan_whole_file(filepath, _NAVIS_PATTERNS)
        if year:
            return f"Navisworks {year}"

    except OSError as e:
        return _read_error('Navisworks', filepath, e)
    except Exception:
        pass
    return "Navisworks (version unknown)"


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------

def write_report(revit_results, navis_results, output_folder):
    date_str   = datetime.now().strftime('%d/%m/%Y')
    file_stamp = datetime.now().strftime('%d%m%y')
    filename   = f"{file_stamp}_BIM_File_Version_Report.txt"
    output_path = os.path.join(output_folder, filename)

    lines = []
    lines.append(f"File Version Report - {date_str}")
    lines.append("=" * 42)
    lines.append("")

    if revit_results:
        for name, version in revit_results:
            lines.append(f"{name} = {version}")
        lines.append("")

    if navis_results:
        for name, version in navis_results:
            lines.append(f"{name} = {version}")
        lines.append("")

    if not revit_results and not navis_results:
        lines.append("No Revit or Navisworks files found.")
        lines.append("")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    scan_paths = [p for p in sys.argv[1:] if os.path.exists(p)]

    if not scan_paths:
        selected = browse_scan_target()
        if not selected:
            messagebox.showinfo("BIM Version Checker", "Nothing selected. Exiting.")
            return
        scan_paths = selected

    revit_files, navis_files = collect_files(scan_paths)

    if not revit_files and not navis_files:
        messagebox.showinfo(
            "BIM Version Checker",
            "No Revit or Navisworks files found in the selected location."
        )
        return

    # Check versions
    revit_results = [(os.path.basename(fp), get_revit_version(fp))  for fp in revit_files]
    navis_results = [(os.path.basename(fp), get_navisworks_version(fp)) for fp in navis_files]

    # Pick output folder
    output_folder = browse_output_folder()
    if not output_folder:
        messagebox.showinfo("BIM Version Checker", "No output folder selected. Exiting.")
        return

    output_path = write_report(revit_results, navis_results, output_folder)

    total = len(revit_results) + len(navis_results)
    messagebox.showinfo(
        "BIM Version Checker",
        f"Done!  {total} file(s) checked.\n\nReport saved to:\n{output_path}"
    )


if __name__ == '__main__':
    main()
