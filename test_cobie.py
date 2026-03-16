# -*- coding: utf-8 -*-
"""
test_cobie.py
-------------
Offline test harness for the COBie_Corrections extension.
Stubs out Autodesk.Revit.DB and System so the library modules can be
imported and exercised on plain CPython / without Revit.

Run:
    python3 test_cobie.py
"""

import sys
import os
import types
import tempfile
import traceback

# ── path setup ───────────────────────────────────────────────────────────────
LIB = os.path.join(os.path.dirname(__file__),
                   'COBie_Corrections.extension', 'lib')
sys.path.insert(0, LIB)

# ─────────────────────────────────────────────────────────────────────────────
# Revit / .NET stubs
# ─────────────────────────────────────────────────────────────────────────────

# --- System.Guid stub --------------------------------------------------------
class _Guid:
    def __init__(self, s): self._s = s
    def __repr__(self): return 'Guid({!r})'.format(self._s)

_system_mod = types.ModuleType('System')
_system_mod.Guid = _Guid
sys.modules['System'] = _system_mod

# --- Autodesk hierarchy stubs ------------------------------------------------
def _make_module(name):
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m

_adesk    = _make_module('Autodesk')
_revit    = _make_module('Autodesk.Revit')
_db       = _make_module('Autodesk.Revit.DB')

class _ElementId:
    def __init__(self, v): self.IntegerValue = v
    def __repr__(self): return 'ElementId({})'.format(self.IntegerValue)

class _FamilySymbol:
    def __init__(self, eid, name, family_name, bic='OST_MechanicalEquipment'):
        self.Id         = _ElementId(eid)
        self.Name       = name
        self.FamilyName = family_name
        self._bic       = bic
        self.Category   = _Category(bic)
    def __repr__(self): return 'FamilySymbol({!r})'.format(self.Name)

class _Category:
    def __init__(self, bic): self.BuiltInCategory = bic; self.Name = bic

class _Transaction:
    def __init__(self, doc, name):
        self._name = name
        self._started = False
        self._ended   = False
    def Start(self):   self._started = True
    def Commit(self):  self._ended   = True
    def RollBack(self):self._ended   = True
    def HasStarted(self): return self._started
    def HasEnded(self):   return self._ended

class _Param:
    def __init__(self, name, value='', read_only=False):
        self._name      = name
        self._value     = value
        self.IsReadOnly = read_only
    def AsString(self): return self._value
    def Set(self, v):   self._value = v

class _ProjectInformation:
    def __init__(self, params):
        # params: dict name->value
        self._params = {k: _Param(k, v) for k, v in params.items()}
    def LookupParameter(self, name):
        return self._params.get(name)
    def get_Parameter(self, guid):
        # find by guid — in real Revit this is GUID-based; here we just
        # search the stub params dict for a matching GUID via cobie_params
        from cobie_params import BY_GUID
        entry = BY_GUID.get(str(guid._s).lower()) if hasattr(guid, '_s') else None
        if entry:
            return self._params.get(entry['name'])
        return None

class _MockDoc:
    def __init__(self, symbols, proj_params):
        self._symbols = symbols          # list of _FamilySymbol
        self.ProjectInformation = _ProjectInformation(proj_params)
    def GetElement(self, eid):
        for sym in self._symbols:
            if sym.Id.IntegerValue == eid.IntegerValue:
                return sym
        return None

class _FilteredElementCollector:
    def __init__(self, doc): self._doc = doc; self._results = list(doc._symbols)
    def OfClass(self, cls):              return self
    def WhereElementIsElementType(self): return self
    def __iter__(self):                  return iter(self._results)

class _BuiltInCategory:
    """Minimal BuiltInCategory stub — just used as a string token."""
    pass

_db.FilteredElementCollector = _FilteredElementCollector
_db.FamilySymbol              = _FamilySymbol
_db.Transaction               = _Transaction
_db.ElementId                 = _ElementId
_db.BuiltInCategory           = _BuiltInCategory

# ─────────────────────────────────────────────────────────────────────────────
# Test helpers
# ─────────────────────────────────────────────────────────────────────────────

PASS = '\033[32mPASS\033[0m'
FAIL = '\033[31mFAIL\033[0m'
_results = []

def check(label, condition, detail=''):
    status = PASS if condition else FAIL
    print('  [{}] {}{}'.format(status, label,
                                '  ({})'.format(detail) if detail else ''))
    _results.append(condition)

def section(title):
    print('\n── {} '.format(title).ljust(70, '─'))

# ─────────────────────────────────────────────────────────────────────────────
# 1. cobie_params
# ─────────────────────────────────────────────────────────────────────────────
section('cobie_params')
try:
    import cobie_params as cp

    check('PARAMS contains all 81 entries', len(cp.PARAMS) == 81,
          'got {}'.format(len(cp.PARAMS)))
    check('BY_GUID has same count as PARAMS', len(cp.BY_GUID) == len(cp.PARAMS))
    check('FACILITY_REQUIRED has 7 entries', len(cp.FACILITY_REQUIRED) == 7)

    for name in cp.FACILITY_REQUIRED:
        g = cp.guid_for(name)
        check('guid_for({}) returns a string'.format(name),
              isinstance(g, str) and len(g) == 36, g or 'None')

    # spot-check a known param
    p = cp.PARAMS.get('COBie.Facility.SiteName')
    check('COBie.Facility.SiteName GUID matches shared param file',
          p and p['guid'] == 'eefeb536-9529-452f-812c-88d9ab919659',
          p['guid'] if p else 'missing')

    p2 = cp.PARAMS.get('COBie.Facility.Description')
    check('COBie.Facility.Description present (was "BuildingDescription")',
          p2 is not None)

    check('BY_GUID reverse lookup works',
          cp.BY_GUID.get('eefeb536-9529-452f-812c-88d9ab919659', {}).get('name')
          == 'COBie.Facility.SiteName')

except Exception:
    print('  IMPORT ERROR:')
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 2. cobie_rules — type name validation
# ─────────────────────────────────────────────────────────────────────────────
section('cobie_rules — validate_type_name')
try:
    import cobie_rules as cr

    # Exact map hits
    issues = cr.validate_type_name(1, 'HeatExchanger_USERDEFINED_Type09')
    check('ExactMap: HeatExchanger_USERDEFINED_Type09 flagged',
          len(issues) == 1 and issues[0]['rule'] == 'ExactMap')
    check('ExactMap: corrected_to is correct',
          issues[0]['corrected_to'] == 'HeatExchanger_UserDefined_Type09')

    issues = cr.validate_type_name(2, 'Tank_Vessel_Type02')
    check('ExactMap: Tank_Vessel_Type02 -> Tank_Expansion_Type02',
          issues[0]['corrected_to'] == 'Tank_Expansion_Type02')

    # Colon format
    issues = cr.validate_type_name(3,
        'BOSS_PipeAccessories_FireControl_DryRiserValves:PN16 65MM')
    check('ExactMap beats ColonFormat for seeded colon name',
          issues[0]['rule'] == 'ExactMap' and
          issues[0]['corrected_to'] == 'FireSuppressionTerminal_DryRiserValve_Type01')

    issues = cr.validate_type_name(4, 'FamilyA:TypeB:ElemC')
    check('ColonFormat: 3-segment colon name flagged',
          any(i['rule'] == 'ColonFormat' for i in issues))
    check('ColonFormat: no auto corrected_to',
          all(i['corrected_to'] == '' for i in issues
              if i['rule'] == 'ColonFormat'))

    # AllCaps
    issues = cr.validate_type_name(5, 'SanitaryTerminal_SHOWER_Type01')
    check('ExactMap: SanitaryTerminal_SHOWER_Type01 caught before AllCaps',
          issues[0]['rule'] == 'ExactMap')

    issues = cr.validate_type_name(6, 'Pump_HOTWATER_Type03')
    check('AllCapsSegment: Pump_HOTWATER_Type03 flagged',
          any(i['rule'] == 'AllCapsSegment' for i in issues))
    check('AllCapsSegment: correction is Pump_Hotwater_Type03',
          any(i['corrected_to'] == 'Pump_Hotwater_Type03' for i in issues))

    # Compliant name
    issues = cr.validate_type_name(7, 'Pump_HotWater_Type03')
    check('Compliant name returns no issues', len(issues) == 0)

    # suggest_correction
    check('suggest_correction returns None for colon-only name',
          cr.suggest_correction('FamilyA:TypeB:ElemC') is None)
    check('suggest_correction returns PascalCase fix for ALLCAPS',
          cr.suggest_correction('Fan_EXTRACT_Type01') == 'Fan_Extract_Type01')
    check('suggest_correction returns exact map entry',
          cr.suggest_correction('Tank_Vessel_Type02') == 'Tank_Expansion_Type02')

except Exception:
    print('  IMPORT ERROR:')
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 3. cobie_rules — validate_project_info
# ─────────────────────────────────────────────────────────────────────────────
section('cobie_rules — validate_project_info')
try:
    # Build a doc where some Facility params are present and some missing/empty
    full_params = {
        'COBie.Facility.SiteName':           'BuildingSite',
        'COBie.Facility.Category':           'Education',
        'COBie.Facility.ProjectName':        'School Block A',
        'COBie.Facility.Phase':              'Phase 1',
        'COBie.Facility.Description':        'Main school building',
        'COBie.Facility.ProjectDescription': 'Renovation project',
        'COBie.Facility.SiteDescription':    'Urban site',
    }
    doc_full = _MockDoc([], full_params)
    issues = cr.validate_project_info(doc_full)
    check('All 7 Facility params present & non-empty → 0 issues',
          len(issues) == 0, 'got {}'.format(len(issues)))

    # Missing two params
    partial_params = {k: v for k, v in full_params.items()
                      if k not in ('COBie.Facility.Phase',
                                   'COBie.Facility.SiteDescription')}
    doc_partial = _MockDoc([], partial_params)
    issues = cr.validate_project_info(doc_partial)
    check('2 missing params → 2 MissingParam issues',
          len(issues) == 2 and
          all(i['rule'].startswith('MissingParam') for i in issues),
          str([i['rule'] for i in issues]))

    # Empty param
    empty_params = dict(full_params)
    empty_params['COBie.Facility.Category'] = ''
    doc_empty = _MockDoc([], empty_params)
    issues = cr.validate_project_info(doc_empty)
    check('Empty param → 1 EmptyParam issue',
          len(issues) == 1 and issues[0]['rule'] == 'EmptyParam:COBie.Facility.Category',
          str([i['rule'] for i in issues]))

except Exception:
    print('  ERROR:')
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 4. cobie_collector
# ─────────────────────────────────────────────────────────────────────────────
section('cobie_collector — collect_issues')
try:
    import cobie_collector as cc

    syms = [
        _FamilySymbol(101, 'HeatExchanger_USERDEFINED_Type09', 'HeatExchanger',
                      'OST_MechanicalEquipment'),
        _FamilySymbol(102, 'Pump_Compliant_Type01', 'Pump',
                      'OST_MechanicalEquipment'),
        _FamilySymbol(103, 'BOSS_PipeAccessories_FireControl_DryRiserValves:PN16 65MM',
                      'BOSS_PipeAccessories', 'OST_PipeAccessory'),
        _FamilySymbol(104, 'Fan_EXTRACT_Type02', 'Fan',
                      'OST_MechanicalEquipment'),
    ]
    doc = _MockDoc(syms, full_params)

    issues = cc.collect_issues(doc)
    elem_ids = [i['element_id'] for i in issues if i['element_id'] is not None]

    check('collect_issues returns a list', isinstance(issues, list))
    check('Compliant type (id=102) not in issues', 102 not in elem_ids)
    check('ExactMap type (id=101) flagged', 101 in elem_ids)
    check('Colon+ExactMap type (id=103) flagged', 103 in elem_ids)
    check('AllCaps type (id=104) flagged', 104 in elem_ids)

    # Category assignment
    cat_101 = next((i['category'] for i in issues if i['element_id'] == 101), None)
    check('OST_MechanicalEquipment maps to Component', cat_101 == 'Component',
          cat_101)

    # family_name enrichment
    fn_101 = next((i.get('family_name') for i in issues
                   if i['element_id'] == 101), None)
    check('family_name enriched on issue', fn_101 == 'HeatExchanger', fn_101)

    # Facility issues from project info (all full_params provided, so 0)
    facility = [i for i in issues if i['category'] == 'Facility']
    check('No Facility issues when all params populated', len(facility) == 0,
          'got {}'.format(len(facility)))

except Exception:
    print('  ERROR:')
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 5. cobie_writer — apply_corrections (write mode)
# ─────────────────────────────────────────────────────────────────────────────
section('cobie_writer — apply_corrections (write mode)')
try:
    import cobie_writer as cw

    syms_w = [
        _FamilySymbol(201, 'HeatExchanger_USERDEFINED_Type09', 'HeatExchanger'),
        _FamilySymbol(202, 'Tank_Vessel_Type02', 'Tank'),
        _FamilySymbol(203, 'Fan_EXTRACT_Type02', 'Fan'),
    ]
    doc_w = _MockDoc(syms_w, full_params)

    confirmed = [
        {'element_id': 201, 'was': 'HeatExchanger_USERDEFINED_Type09',
         'corrected_to': 'HeatExchanger_UserDefined_Type09',
         'category': 'Component', 'rule': 'ExactMap',
         'type_name': 'HeatExchanger_USERDEFINED_Type09', 'family_name': 'HeatExchanger'},
        {'element_id': 202, 'was': 'Tank_Vessel_Type02',
         'corrected_to': 'Tank_Expansion_Type02',
         'category': 'Component', 'rule': 'ExactMap',
         'type_name': 'Tank_Vessel_Type02', 'family_name': 'Tank'},
        {'element_id': 203, 'was': 'Fan_EXTRACT_Type02',
         'corrected_to': 'Fan_Extract_Type02',
         'category': 'Component', 'rule': 'AllCapsSegment',
         'type_name': 'Fan_EXTRACT_Type02', 'family_name': 'Fan'},
    ]

    result = cw.apply_corrections(doc_w, confirmed, dry_run=False)
    check('applied == 3', result['applied'] == 3,
          'applied={} skipped={} failed={}'.format(
              result['applied'], result['skipped'], result['failed']))
    check('skipped == 0', result['skipped'] == 0)
    check('failed  == []', result['failed']  == [])
    check('dry_run == False', result['dry_run'] == False)

    # verify names actually changed on the stubs
    sym201 = doc_w.GetElement(_ElementId(201))
    check('sym 201 Name written correctly',
          sym201.Name == 'HeatExchanger_UserDefined_Type09', sym201.Name)
    sym202 = doc_w.GetElement(_ElementId(202))
    check('sym 202 Name written correctly',
          sym202.Name == 'Tank_Expansion_Type02', sym202.Name)

except Exception:
    print('  ERROR:')
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 6. cobie_writer — collision detection
# ─────────────────────────────────────────────────────────────────────────────
section('cobie_writer — collision detection')
try:
    syms_c = [
        _FamilySymbol(301, 'Tank_Vessel_Type02', 'Tank'),
        _FamilySymbol(302, 'Tank_Expansion_Type02', 'Tank'),  # target already exists
    ]
    doc_c = _MockDoc(syms_c, full_params)

    confirmed_c = [{
        'element_id': 301, 'was': 'Tank_Vessel_Type02',
        'corrected_to': 'Tank_Expansion_Type02',   # collides with id=302
        'category': 'Component', 'rule': 'ExactMap',
        'type_name': 'Tank_Vessel_Type02', 'family_name': 'Tank',
    }]
    result_c = cw.apply_corrections(doc_c, confirmed_c, dry_run=False)
    check('Collision → 0 applied, 1 failed',
          result_c['applied'] == 0 and len(result_c['failed']) == 1,
          str(result_c['failed']))
    check('Failure message mentions target name',
          'Tank_Expansion_Type02' in result_c['failed'][0])

except Exception:
    print('  ERROR:')
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 7. cobie_writer — external rename guard
# ─────────────────────────────────────────────────────────────────────────────
section('cobie_writer — external rename guard')
try:
    syms_e = [_FamilySymbol(401, 'AlreadyRenamed_Type01', 'Fan')]
    doc_e  = _MockDoc(syms_e, full_params)

    confirmed_e = [{
        'element_id': 401,
        'was': 'Fan_EXTRACT_Type02',           # stale — model already changed
        'corrected_to': 'Fan_Extract_Type02',
        'category': 'Component', 'rule': 'AllCapsSegment',
        'type_name': 'Fan_EXTRACT_Type02', 'family_name': 'Fan',
    }]
    result_e = cw.apply_corrections(doc_e, confirmed_e, dry_run=False)
    check('Stale issue → skipped, not applied',
          result_e['applied'] == 0 and result_e['skipped'] == 1,
          str(result_e))

except Exception:
    print('  ERROR:')
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 8. cobie_writer — dry_run mode
# ─────────────────────────────────────────────────────────────────────────────
section('cobie_writer — dry_run mode')
try:
    syms_d = [_FamilySymbol(501, 'HeatExchanger_USERDEFINED_Type09', 'HX')]
    doc_d  = _MockDoc(syms_d, full_params)

    confirmed_d = [{
        'element_id': 501, 'was': 'HeatExchanger_USERDEFINED_Type09',
        'corrected_to': 'HeatExchanger_UserDefined_Type09',
        'category': 'Component', 'rule': 'ExactMap',
        'type_name': 'HeatExchanger_USERDEFINED_Type09', 'family_name': 'HX',
    }]

    import io
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured

    result_d = cw.apply_corrections(doc_d, confirmed_d, dry_run=True)

    sys.stdout = old_stdout
    log_output = captured.getvalue()

    check('dry_run result flag is True', result_d['dry_run'] == True)
    check('dry_run applied count == 1', result_d['applied'] == 1)
    check('dry_run: name NOT changed on stub',
          doc_d.GetElement(_ElementId(501)).Name
          == 'HeatExchanger_USERDEFINED_Type09')
    check('dry_run: [DRY RUN] logged to stdout',
          '[DRY RUN]' in log_output, repr(log_output[:120]))

except Exception:
    print('  ERROR:')
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 9. cobie_writer — no-fix skip
# ─────────────────────────────────────────────────────────────────────────────
section('cobie_writer — no-fix items skipped')
try:
    syms_n = [_FamilySymbol(601, 'FamilyA:TypeB:ElemC', 'Fam')]
    doc_n  = _MockDoc(syms_n, full_params)

    confirmed_n = [{
        'element_id': 601, 'was': 'FamilyA:TypeB:ElemC',
        'corrected_to': '',   # ColonFormat has no auto-fix
        'category': 'Component', 'rule': 'ColonFormat',
        'type_name': 'FamilyA:TypeB:ElemC', 'family_name': 'Fam',
    }]
    result_n = cw.apply_corrections(doc_n, confirmed_n, dry_run=False)
    check('Empty corrected_to → skipped with failure message',
          result_n['applied'] == 0 and result_n['skipped'] == 1,
          str(result_n))

except Exception:
    print('  ERROR:')
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# 10. cobie_writer — export_csv
# ─────────────────────────────────────────────────────────────────────────────
section('cobie_writer — export_csv')
try:
    import csv

    sample_issues = [
        {'category': 'Component', 'family_name': 'HX', 'element_id': 101,
         'was': 'HeatExchanger_USERDEFINED_Type09',
         'corrected_to': 'HeatExchanger_UserDefined_Type09', 'rule': 'ExactMap'},
        {'category': 'Facility', 'family_name': '', 'element_id': None,
         'was': '<empty>', 'corrected_to': '<provide value for "COBie.Facility.Phase">',
         'rule': 'EmptyParam:COBie.Facility.Phase'},
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                     delete=False, newline='') as tf:
        tmp_path = tf.name

    cw.export_csv(sample_issues, tmp_path)

    with open(tmp_path, newline='') as fh:
        rows = list(csv.DictReader(fh))

    check('CSV has 2 data rows', len(rows) == 2, 'got {}'.format(len(rows)))
    check('CSV header: Category column present', 'Category' in rows[0])
    check('CSV header: all 6 columns present',
          set(rows[0].keys()) == {'Category','FamilyName','ElementID',
                                   'Was','CorrectedTo','Rule'})
    check('CSV row 0 Was value correct',
          rows[0]['Was'] == 'HeatExchanger_USERDEFINED_Type09')
    check('CSV row 1 ElementID is empty string for None',
          rows[1]['ElementID'] == '')

    os.unlink(tmp_path)

except Exception:
    print('  ERROR:')
    traceback.print_exc()

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
total  = len(_results)
passed = sum(_results)
failed = total - passed
print('\n' + '═' * 70)
print('Result: {}/{} passed{}'.format(
    passed, total,
    '  ✓ all green' if failed == 0 else
    '  ✗ {} FAILED'.format(failed)))
print('═' * 70)
sys.exit(0 if failed == 0 else 1)
