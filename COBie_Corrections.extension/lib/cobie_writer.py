# -*- coding: utf-8 -*-
"""
cobie_writer.py
---------------
Writes confirmed COBie corrections back to the Revit document.

Public API
----------
apply_corrections(doc, confirmed_issues, dry_run=False) -> SummaryResult
export_csv(issues, filepath) -> str

confirmed_issues  : list of Issue dicts (same shape as cobie_collector output)
                    Only issues whose 'corrected_to' is a non-empty string and
                    that have been checked by the user are passed in.

SummaryResult is a dict:
    applied  : int
    skipped  : int
    failed   : list[str]   (human-readable failure messages)
    dry_run  : bool        (True when no writes were performed)
"""

import sys
import csv as _csv

from cobie_params import guid_for

try:
    from Autodesk.Revit.DB import (
        Transaction,
        FilteredElementCollector,
        FamilySymbol,
        ElementId,
    )
    from System import Guid as _Guid
    _REVIT_AVAILABLE = True
except ImportError:
    _REVIT_AVAILABLE = False

TRANSACTION_NAME = 'COBie Compliance Corrections'


# ---------------------------------------------------------------------------
# Dry-run logger
# ---------------------------------------------------------------------------

def _log_dry(msg):
    """Write a dry-run log line to stdout (pyRevit output panel picks this up)."""
    sys.stdout.write(msg + '\n')


# ---------------------------------------------------------------------------
# Collision detection
# ---------------------------------------------------------------------------

def _existing_type_names(doc):
    """Return a set of all current FamilySymbol.Name values in the document."""
    names = set()
    collector = (
        FilteredElementCollector(doc)
        .OfClass(FamilySymbol)
        .WhereElementIsElementType()
    )
    for sym in collector:
        try:
            names.add(sym.Name)
        except Exception:
            pass
    return names


def _get_symbol(doc, element_id_int):
    """Retrieve a FamilySymbol by integer element id."""
    eid = ElementId(element_id_int)
    elem = doc.GetElement(eid)
    if elem is None:
        raise KeyError('Element id {} not found in document.'.format(element_id_int))
    if not isinstance(elem, FamilySymbol):
        raise TypeError(
            'Element id {} is not a FamilySymbol (got {}).'.format(
                element_id_int, type(elem).__name__
            )
        )
    return elem


# ---------------------------------------------------------------------------
# ProjectInformation writer
# ---------------------------------------------------------------------------

def _apply_project_info_correction(doc, issue):
    """
    Apply a single project-information correction.

    Parameter lookup order:
      1. GUID-based  (element.get_Parameter(System.Guid)) — most reliable;
         GUID sourced from cobie_params.guid_for(param_name).
      2. Name-based  (LookupParameter) — fallback if GUID lookup returns None.

    Returns True on success, raises on failure.
    """
    # Rule string is 'MissingParam:COBie.Facility.SiteName' or 'EmptyParam:...'
    param_name = issue['rule'].split(':', 1)[-1]
    new_value  = issue['corrected_to']

    # corrected_to for missing/empty params is a placeholder instruction;
    # we cannot auto-fill those — skip with a clear message.
    if new_value.startswith('<'):
        raise ValueError(
            'Parameter "{}" requires manual entry — cannot auto-correct.'.format(
                param_name
            )
        )

    proj  = doc.ProjectInformation
    param = None

    # 1. GUID lookup
    guid_str = guid_for(param_name)
    if guid_str:
        try:
            param = proj.get_Parameter(_Guid(guid_str))
        except Exception:
            param = None

    # 2. Name fallback
    if param is None:
        param = proj.LookupParameter(param_name)

    if param is None:
        raise KeyError(
            'Shared parameter "{}" (guid={}) not found on ProjectInformation.'.format(
                param_name, guid_str or 'unknown'
            )
        )
    if param.IsReadOnly:
        raise PermissionError(
            'Parameter "{}" is read-only.'.format(param_name)
        )

    param.Set(new_value)
    return True


# ---------------------------------------------------------------------------
# Main writer
# ---------------------------------------------------------------------------

def apply_corrections(doc, confirmed_issues, dry_run=False):
    """
    Write all confirmed corrections inside a single named transaction.

    When dry_run=True, all validation logic (collision detection, external-change
    guards, element lookups) runs normally but no writes are made to the model.
    Each planned change is logged to stdout with a [DRY RUN] prefix so it
    appears in pyRevit's output panel.

    Parameters
    ----------
    doc               : Autodesk.Revit.DB.Document
    confirmed_issues  : list[Issue]  — only checked, non-empty corrected_to items
    dry_run           : bool         — when True, simulate only; no writes

    Returns
    -------
    dict with keys: applied (int), skipped (int), failed (list[str]), dry_run (bool)
    """
    if not _REVIT_AVAILABLE:
        raise EnvironmentError(
            'Revit API not available. Run this script inside pyRevit/Revit.'
        )

    applied = 0
    skipped = 0
    failed  = []

    # Pre-flight: filter out issues with no actionable correction
    actionable = []
    for issue in confirmed_issues:
        corrected_to = (issue.get('corrected_to') or '').strip()
        if not corrected_to or corrected_to.startswith('<'):
            skipped += 1
            failed.append(
                '[SKIP] "{}" — no automatic correction available.'.format(
                    issue.get('was', '?')
                )
            )
        else:
            actionable.append(issue)

    if not actionable:
        return {'applied': 0, 'skipped': skipped, 'failed': failed, 'dry_run': dry_run}

    # Snapshot existing names for collision detection (pre-transaction)
    existing_names = _existing_type_names(doc)

    if dry_run:
        _log_dry('=== COBie Dry Run — {} planned correction(s) ==='.format(
            len(actionable)))

    # Open transaction only in write mode
    t = None
    if not dry_run:
        t = Transaction(doc, TRANSACTION_NAME)

    try:
        if not dry_run:
            t.Start()

        for issue in actionable:
            was          = issue.get('was', '')
            corrected_to = issue['corrected_to'].strip()
            elem_id      = issue.get('element_id')
            rule         = issue.get('rule', '')

            try:
                # ---- ProjectInformation issues ----
                if elem_id is None:
                    if dry_run:
                        param_name = rule.split(':', 1)[-1]
                        _log_dry(
                            '[DRY RUN] Would set ProjectInformation param '
                            '"{}" → "{}"'.format(param_name, corrected_to)
                        )
                    else:
                        _apply_project_info_correction(doc, issue)
                    applied += 1
                    continue

                # ---- FamilySymbol rename ----
                # Collision detection (runs in both modes)
                if corrected_to in existing_names and corrected_to != was:
                    raise ValueError(
                        'Target name "{}" already exists in the model.'.format(
                            corrected_to
                        )
                    )

                sym = _get_symbol(doc, elem_id)

                # Guard: name hasn't changed since collection (another session?)
                if sym.Name != was:
                    skipped += 1
                    failed.append(
                        '[SKIP] ElementId {} name changed externally '
                        '("{}" -> "{}", expected "{}"). Skipped.'.format(
                            elem_id, was, sym.Name, corrected_to
                        )
                    )
                    continue

                if dry_run:
                    _log_dry(
                        '[DRY RUN] Would rename (id={}, rule={}): '
                        '"{}" → "{}"'.format(elem_id, rule, was, corrected_to)
                    )
                else:
                    sym.Name = corrected_to

                # Update collision set so subsequent checks in the same loop are safe
                existing_names.discard(was)
                existing_names.add(corrected_to)
                applied += 1

            except Exception as exc:
                failed.append(
                    '[FAIL] "{}" (id={}, rule={}): {}'.format(
                        was, elem_id, rule, exc
                    )
                )

        if not dry_run:
            t.Commit()

    except Exception as tx_exc:
        # Roll back the transaction on unexpected error (write mode only)
        if t is not None and t.HasStarted() and not t.HasEnded():
            t.RollBack()
        raise RuntimeError(
            'Transaction "{}" rolled back: {}'.format(TRANSACTION_NAME, tx_exc)
        )

    if dry_run:
        _log_dry('=== Dry Run complete: {} would apply, {} skipped, {} failed ==='.format(
            applied, skipped, len(failed)))

    return {
        'applied': applied,
        'skipped': skipped,
        'failed':  failed,
        'dry_run': dry_run,
    }


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def export_csv(issues, filepath):
    """
    Write all collected Issue dicts to a CSV file (full audit trail).

    Exports every issue regardless of checkbox state, giving a complete
    picture of everything the validator found.

    Parameters
    ----------
    issues   : list[Issue]  — raw list from collect_issues()
    filepath : str          — absolute path to write (overwritten if exists)

    Returns
    -------
    str — the filepath written
    """
    fieldnames = ['Category', 'FamilyName', 'ElementID', 'Was', 'CorrectedTo', 'Rule']
    with open(filepath, 'w', newline='') as fh:
        writer = _csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for issue in issues:
            writer.writerow({
                'Category':    issue.get('category', ''),
                'FamilyName':  issue.get('family_name', ''),
                'ElementID':   issue.get('element_id', ''),
                'Was':         issue.get('was', ''),
                'CorrectedTo': issue.get('corrected_to', ''),
                'Rule':        issue.get('rule', ''),
            })
    return filepath
