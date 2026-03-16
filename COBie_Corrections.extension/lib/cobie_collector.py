# -*- coding: utf-8 -*-
"""
cobie_collector.py
------------------
Gathers FamilySymbol elements and ProjectInformation from the active Revit
document, then runs them through the rule engine.

Public API
----------
collect_issues(doc) -> list[Issue]
    Returns every Issue dict produced by the rule engine, enriched with the
    Revit BuiltInCategory name so the UI can assign the COBie group.

Each Issue dict has at minimum:
    element_id   : int | None
    category     : str   ("Facility" | "Floor" | "Type" | "Component")
    was          : str
    corrected_to : str
    rule         : str
    type_name    : str   (display name — same as 'was' for type issues)
    family_name  : str   (parent family name, or '' for project-info issues)
"""

import sys

# ---------------------------------------------------------------------------
# Revit API imports — only available when running inside pyRevit/Revit
# ---------------------------------------------------------------------------
try:
    from Autodesk.Revit.DB import (
        FilteredElementCollector,
        FamilySymbol,
        BuiltInCategory,
    )
    _REVIT_AVAILABLE = True
except ImportError:
    _REVIT_AVAILABLE = False

from cobie_rules import validate_type_name, validate_project_info

# ---------------------------------------------------------------------------
# COBie category grouping
# BuiltInCategory values mapped to COBie groups.
# Unmapped categories default to "Component".
# ---------------------------------------------------------------------------

_COBIE_GROUP = {
    # Facility-level (site / building)
    'OST_ProjectBasePoint':   'Facility',
    'OST_SurveyPoint':        'Facility',

    # Floor-level
    'OST_Levels':             'Floor',
    'OST_Floors':             'Floor',
    'OST_Ceilings':           'Floor',
    'OST_Roofs':              'Floor',

    # Architectural finish types -> Type group
    'OST_Walls':              'Type',
    'OST_Doors':              'Type',
    'OST_Windows':            'Type',
    'OST_Stairs':             'Type',
    'OST_Ramps':              'Type',
    'OST_Columns':            'Type',
    'OST_StructuralColumns':  'Type',
    'OST_StructuralFraming':  'Type',

    # MEP -> Component
    'OST_MechanicalEquipment':'Component',
    'OST_PlumbingFixtures':   'Component',
    'OST_ElectricalEquipment':'Component',
    'OST_ElectricalFixtures': 'Component',
    'OST_LightingFixtures':   'Component',
    'OST_FireAlarmDevices':   'Component',
    'OST_SecurityDevices':    'Component',
    'OST_DataDevices':        'Component',
    'OST_CommunicationDevices':'Component',
    'OST_NurseCallDevices':   'Component',
    'OST_Sprinklers':         'Component',
    'OST_DuctTerminal':       'Component',
    'OST_DuctAccessory':      'Component',
    'OST_PipeAccessory':      'Component',
    'OST_PipeFitting':        'Component',
    'OST_DuctFitting':        'Component',
    'OST_GenericModel':       'Component',
    'OST_Furniture':          'Component',
    'OST_FurnitureSystems':   'Component',
    'OST_CurtainWallPanels':  'Component',
    'OST_Casework':           'Component',
    'OST_SpecialtyEquipment': 'Component',
}


def _get_cobie_group(family_symbol):
    """Return the COBie group string for a FamilySymbol."""
    try:
        cat_name = family_symbol.Category.Name  # e.g. "Mechanical Equipment"
        # Build an OST_ key from the category enum value name
        bic = family_symbol.Category.BuiltInCategory
        bic_name = str(bic)  # e.g. "OST_MechanicalEquipment"
        return _COBIE_GROUP.get(bic_name, 'Component')
    except Exception:
        return 'Component'


# ---------------------------------------------------------------------------
# Main collection function
# ---------------------------------------------------------------------------

def collect_issues(doc):
    """
    Collect all FamilySymbol type names and ProjectInformation parameters,
    validate them, and return a flat list of Issue dicts.
    """
    if not _REVIT_AVAILABLE:
        raise EnvironmentError(
            'Revit API not available. Run this script inside pyRevit/Revit.'
        )

    issues = []

    # ------------------------------------------------------------------
    # 1. FamilySymbol type names
    # ------------------------------------------------------------------
    collector = (
        FilteredElementCollector(doc)
        .OfClass(FamilySymbol)
        .WhereElementIsElementType()
    )

    for sym in collector:
        try:
            type_name   = sym.Name                       # built-in Type Name
            family_name = sym.FamilyName
            elem_id     = sym.Id.IntegerValue
            cobie_group = _get_cobie_group(sym)

            for issue in validate_type_name(elem_id, type_name, cobie_group):
                issue['type_name']   = type_name
                issue['family_name'] = family_name
                issues.append(issue)

        except Exception as exc:
            # Skip elements that throw (e.g. corrupt families)
            sys.stderr.write(
                'COBie collector: skipping element {}: {}\n'.format(
                    getattr(sym, 'Id', '?'), exc
                )
            )

    # ------------------------------------------------------------------
    # 2. ProjectInformation shared parameters
    # ------------------------------------------------------------------
    for issue in validate_project_info(doc):
        issue['type_name']   = issue['rule']   # human-readable label
        issue['family_name'] = ''
        issues.append(issue)

    return issues
