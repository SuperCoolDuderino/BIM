# -*- coding: utf-8 -*-
"""
cobie_writer.py
---------------
Writes confirmed COBie corrections back to the Revit document.

Public API
----------
apply_corrections(doc, confirmed_issues) -> SummaryResult

confirmed_issues  : list of Issue dicts (same shape as cobie_collector output)
                    Only issues whose 'corrected_to' is a non-empty string and
                    that have been checked by the user are passed in.

SummaryResult is a dict:
    applied : int
    skipped : int
    failed  : list[str]   (human-readable failure messages)
"""

import sys

try:
    from Autodesk.Revit.DB import (
        Transaction,
        FilteredElementCollector,
        FamilySymbol,
        ElementId,
    )
    _REVIT_AVAILABLE = True
except ImportError:
    _REVIT_AVAILABLE = False

TRANSACTION_NAME = 'COBie Compliance Corrections'


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
    Returns True on success, raises on failure.
    """
    param_name = issue['rule'].split(':', 1)[-1]   # e.g. 'SiteName'
    new_value  = issue['corrected_to']

    # corrected_to for missing/empty params is a placeholder instruction;
    # we cannot auto-fill those — skip with a clear message.
    if new_value.startswith('<'):
        raise ValueError(
            'Parameter "{}" requires manual entry — cannot auto-correct.'.format(
                param_name
            )
        )

    param = doc.ProjectInformation.LookupParameter(param_name)
    if param is None:
        raise KeyError(
            'Shared parameter "{}" not found on ProjectInformation.'.format(
                param_name
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

def apply_corrections(doc, confirmed_issues):
    """
    Write all confirmed corrections inside a single named transaction.

    Parameters
    ----------
    doc               : Autodesk.Revit.DB.Document
    confirmed_issues  : list[Issue]  — only checked, non-empty corrected_to items

    Returns
    -------
    dict with keys: applied (int), skipped (int), failed (list[str])
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
        return {'applied': 0, 'skipped': skipped, 'failed': failed}

    # Snapshot existing names for collision detection (pre-transaction)
    existing_names = _existing_type_names(doc)

    t = Transaction(doc, TRANSACTION_NAME)
    try:
        t.Start()

        for issue in actionable:
            was          = issue.get('was', '')
            corrected_to = issue['corrected_to'].strip()
            elem_id      = issue.get('element_id')
            rule         = issue.get('rule', '')

            try:
                # ---- ProjectInformation issues ----
                if elem_id is None:
                    _apply_project_info_correction(doc, issue)
                    applied += 1
                    continue

                # ---- FamilySymbol rename ----
                # Collision detection
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

                sym.Name = corrected_to
                # Update collision set so subsequent renames in same tx are safe
                existing_names.discard(was)
                existing_names.add(corrected_to)
                applied += 1

            except Exception as exc:
                failed.append(
                    '[FAIL] "{}" (id={}, rule={}): {}'.format(
                        was, elem_id, rule, exc
                    )
                )

        t.Commit()

    except Exception as tx_exc:
        # Roll back the entire transaction on unexpected error
        if t.HasStarted() and not t.HasEnded():
            t.RollBack()
        raise RuntimeError(
            'Transaction "{}" rolled back: {}'.format(TRANSACTION_NAME, tx_exc)
        )

    return {
        'applied': applied,
        'skipped': skipped,
        'failed':  failed,
    }
