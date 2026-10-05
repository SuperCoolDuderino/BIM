#!/usr/bin/env python3
"""
BIM Version Checker - diagnostic helper.
Drag one or more Revit files onto this script (or run it and paste a path).
Writes 'bim_version_diagnose_report.txt' next to this script. The report
contains only technical details (sizes, error messages, the Revit version
header text) - no model geometry or project data beyond the file path.

Keep this file in the same folder as bim_version_checker.py.
"""

import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPORT = os.path.join(HERE, 'bim_version_diagnose_report.txt')


def diagnose(path, out):
    out.append('=' * 70)
    out.append(f'File: {path}')

    # Step 1: basic file system info
    try:
        st = os.stat(path)
        out.append(f'Size: {st.st_size:,} bytes')
        attrs = getattr(st, 'st_file_attributes', None)
        if attrs is not None:
            out.append(f'Windows attributes: 0x{attrs:08X}'
                       + ('  (OFFLINE/cloud placeholder flag set)' if attrs & 0x1000 else '')
                       + ('  (RECALL_ON_DATA_ACCESS - cloud-only)' if attrs & 0x400000 else ''))
    except Exception:
        out.append('STEP 1 (stat) FAILED:')
        out.append(traceback.format_exc())
        return

    # Step 2: can Python open and read the file at all?
    try:
        with open(path, 'rb') as f:
            head = f.read(8)
        out.append(f'First 8 bytes: {head!r}  '
                   + ('(compound file signature OK)'
                      if head == b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1' else '(NOT a compound file)'))
    except Exception:
        out.append('STEP 2 (open/read) FAILED - Windows cannot read this file:')
        out.append(traceback.format_exc())
        return

    # Step 3: parse the compound file and read BasicFileInfo
    try:
        import bim_version_checker as bvc
    except Exception:
        out.append('Could not import bim_version_checker.py - is it in the same folder?')
        out.append(traceback.format_exc())
        return
    try:
        with open(path, 'rb') as f:
            cfb = bvc.CompoundFile(f)
            out.append(f'Sector size: {cfb.sector_size}, FAT entries: {len(cfb.fat):,}, '
                       f'directory entries: {len(cfb.entries)}')
            out.append(f'Streams: {cfb.stream_names()}')
            info = cfb.read_stream('BasicFileInfo')
        if info is None:
            out.append('No BasicFileInfo stream found.')
        else:
            out.append(f'BasicFileInfo: {len(info)} bytes. Text (both alignments):')
            for off in (0, 1):
                text = info[off:].decode('utf-16-le', errors='replace')
                text = ''.join(c if (' ' <= c <= '~' or c in '\r\n') else '.' for c in text)
                lines = [ln.strip('.')[-100:] for ln in text.splitlines()
                         if any(k in ln for k in ('Format:', 'Revit', 'Build:', 'Worksharing'))]
                out.append(f'  offset {off}: ' + (' | '.join(lines) or '(nothing readable)'))
    except Exception:
        out.append('STEP 3 (compound file parse) FAILED:')
        out.append(traceback.format_exc())

    # Step 4: the result the main checker would report
    try:
        out.append(f'Checker result: {bvc.get_revit_version(path)}')
    except Exception:
        out.append('STEP 4 (get_revit_version) FAILED:')
        out.append(traceback.format_exc())


def main():
    paths = [p for p in sys.argv[1:]]
    if not paths:
        p = input('Paste the full path of a Revit file and press Enter:\n> ').strip().strip('"')
        paths = [p]
    out = [f'Python {sys.version}', f'Platform: {sys.platform}']
    for p in paths:
        diagnose(p, out)
    with open(REPORT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print('\n'.join(out))
    print(f'\nReport saved to: {REPORT}')
    input('\nPress Enter to close...')


if __name__ == '__main__':
    main()
