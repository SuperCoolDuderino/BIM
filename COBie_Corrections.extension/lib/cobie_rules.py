# -*- coding: utf-8 -*-
"""
cobie_rules.py
--------------
Rule engine for COBie compliance validation.

Exposes:
    validate_type_name(element_id_int, name, category_group) -> list[Issue]
    validate_project_info(doc)                                -> list[Issue]
    suggest_correction(name)                                  -> str | None

Issue is a dict with keys:
    element_id   : int  (ElementId.IntegerValue, or None for project info)
    category     : str  ("Facility" | "Floor" | "Type" | "Component")
    was          : str  (current value)
    corrected_to : str  (suggested value)
    rule         : str  (short rule label)

Parameter lookup strategy
-------------------------
ProjectInformation shared parameters are looked up by GUID (via
element.get_Parameter(System.Guid(guid_string))) rather than by display name.
This is robust against localisations, renames, and duplicate-name collisions.
GUIDs are sourced from cobie_params.py, which was transcribed verbatim from
the project's COBie shared parameter file.
"""

import re

from cobie_params import FACILITY_REQUIRED, guid_for

# ---------------------------------------------------------------------------
# Generic regex rules (fire on every model)
# ---------------------------------------------------------------------------

# Colon-format names: Family:Type:ElementID  (3+ colon-separated segments)
COLON_FORMAT = re.compile(r'.+:.+:.+')

# ALL-CAPS segment inside underscored name, e.g. _USERDEFINED_ or _SHOWER_
ALLCAPS_SEGMENT = re.compile(r'_([A-Z]{3,})_')

# ---------------------------------------------------------------------------
# Seeded correction map (exact-match overrides)
# ---------------------------------------------------------------------------

TYPE_MAP = {
    'HeatExchanger_USERDEFINED_Type09':                           'HeatExchanger_UserDefined_Type09',
    'SanitaryTerminal_SHOWER_Type01':                             'SanitaryTerminal_Shower_Type01',
    'BOSS_PipeAccessories_FireControl_DryRiserValves:PN16 65MM':  'FireSuppressionTerminal_DryRiserValve_Type01',
    'ElectricApplicance_AlarmPanel_Type04':                       'ElectricAppliance_AlarmPanel_Type04',
    'ElectricApplicance_Camera_Type01':                           'ElectricAppliance_Camera_Type01',
    'Tank_Vessel_Type02':                                         'Tank_Expansion_Type02',
}

# ---------------------------------------------------------------------------
# Helper: PascalCase converter for a single all-caps token
# ---------------------------------------------------------------------------

def _to_pascal(token):
    """Convert e.g. 'USERDEFINED' -> 'Userdefined' (simple title-case)."""
    return token.capitalize()


def _fix_allcaps_segments(name):
    """Replace every _ALLCAPS_ segment with its PascalCase equivalent."""
    def repl(m):
        return '_{}_'.format(_to_pascal(m.group(1)))
    return ALLCAPS_SEGMENT.sub(repl, name)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def suggest_correction(name):
    """
    Return a corrected string for *name*, or None if no correction is needed.

    Priority:
      1. Exact match in TYPE_MAP
      2. COLON_FORMAT  -> no automatic rename; returns None (must be flagged)
      3. ALLCAPS_SEGMENT -> apply _to_pascal on matching segments
    """
    if name in TYPE_MAP:
        return TYPE_MAP[name]
    if COLON_FORMAT.match(name):
        return None
    if ALLCAPS_SEGMENT.search(name):
        return _fix_allcaps_segments(name)
    return None


def validate_type_name(element_id_int, name, category_group='Type'):
    """
    Validate a single FamilySymbol type name.

    Returns a list of Issue dicts (empty if compliant).
    """
    issues = []

    # Exact-map hit (includes colon-format renames)
    if name in TYPE_MAP:
        issues.append({
            'element_id':   element_id_int,
            'category':     category_group,
            'was':          name,
            'corrected_to': TYPE_MAP[name],
            'rule':         'ExactMap',
        })
        return issues  # exact map wins; no further checks

    # Colon-format check
    if COLON_FORMAT.match(name):
        issues.append({
            'element_id':   element_id_int,
            'category':     category_group,
            'was':          name,
            'corrected_to': '',   # no auto-fix; user must supply
            'rule':         'ColonFormat',
        })

    # All-caps segment check (can co-exist with colon check)
    if ALLCAPS_SEGMENT.search(name):
        issues.append({
            'element_id':   element_id_int,
            'category':     category_group,
            'was':          name,
            'corrected_to': _fix_allcaps_segments(name),
            'rule':         'AllCapsSegment',
        })

    return issues


def validate_project_info(doc):
    """
    Validate ProjectInformation shared parameters against AIR rules.

    Parameters are looked up by GUID (sourced from cobie_params.py) so the
    check is robust against display-name variations. FACILITY_REQUIRED lists
    the seven AIR-mandatory parameters using their canonical shared-param names.

    Returns a list of Issue dicts (category='Facility').
    """
    # Revit API GUID import — only available inside pyRevit/Revit
    try:
        from System import Guid as _Guid
        _guid_lookup_available = True
    except ImportError:
        _guid_lookup_available = False

    issues = []
    proj   = doc.ProjectInformation

    for param_name in FACILITY_REQUIRED:
        param = None
        guid_str = guid_for(param_name)

        # Primary: GUID-based lookup (most reliable)
        if _guid_lookup_available and guid_str:
            try:
                param = proj.get_Parameter(_Guid(guid_str))
            except Exception:
                param = None

        # Fallback: name-based lookup (works if GUID lookup not available)
        if param is None:
            param = proj.LookupParameter(param_name)

        if param is None:
            issues.append({
                'element_id':   None,
                'category':     'Facility',
                'was':          '<missing>',
                'corrected_to': '<add shared parameter "{}">'.format(param_name),
                'rule':         'MissingParam:{}'.format(param_name),
            })
            continue

        value = param.AsString() or ''
        if not value.strip():
            issues.append({
                'element_id':   None,
                'category':     'Facility',
                'was':          '<empty>',
                'corrected_to': '<provide value for "{}">'.format(param_name),
                'rule':         'EmptyParam:{}'.format(param_name),
            })

    return issues
