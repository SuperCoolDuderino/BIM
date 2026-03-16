# -*- coding: utf-8 -*-
"""
cobie_params.py
---------------
Parsed representation of the COBie Revit shared parameter file.

Provides:
    PARAMS          : dict[name -> ParamDef]  — all parameters, keyed by full name
    BY_GUID         : dict[guid_str -> ParamDef]  — fast reverse lookup
    FACILITY_REQUIRED : list[str]  — full names of AIR-mandatory Facility params

ParamDef is a dict with keys:
    name      : str   (e.g. 'COBie.Facility.SiteName')
    guid      : str   (lowercase hyphenated UUID string)
    datatype  : str   (e.g. 'TEXT', 'LENGTH', 'AREA', 'YESNO', 'CURRENCY')
    group_id  : int   (Revit shared-param group id)
    group     : str   (e.g. 'COBie.Facility')

Source: COBie shared parameter file, VERSION 2 / MINVERSION 1.
"""

# ---------------------------------------------------------------------------
# Group id -> COBie group name map (from *GROUP section of the .txt)
# ---------------------------------------------------------------------------
_GROUPS = {
    1: 'COBie',
    3: 'COBie.Component',
    4: 'COBie.Facility',
    5: 'COBie.Floor',
    6: 'COBie.Space',
    7: 'COBie.System',
    8: 'COBie.Type',
    9: 'COBie.Zone',
}

# ---------------------------------------------------------------------------
# Raw param table  (guid, name, datatype, group_id)
# Transcribed verbatim from the shared parameter .txt file.
# ---------------------------------------------------------------------------
_RAW = [
    # ── COBie (group 1) ────────────────────────────────────────────────────
    ('fc95531f-3d82-40c6-b03f-c6a7cf97b828', 'COBie.CreatedBy',                          'TEXT',     1),
    ('4b888e29-dfb5-4b06-a270-9d59c62e6077', 'COBie.CreatedOn',                          'TEXT',     1),
    ('a4a71d65-98ff-466f-9c70-d8d281aae297', 'COBie',                                    'YESNO',    1),
    ('bc1ccde3-5d86-42eb-ae1f-8344f730fa26', 'COBie.ExternalIdentifier',                 'TEXT',     1),

    # ── COBie.Component (group 3) ──────────────────────────────────────────
    ('db949116-a361-4876-be1d-fe82769fc860', 'COBie.Component.SerialNumber',              'TEXT',     3),
    ('fea46332-2c3d-474b-9016-b1d649d76184', 'COBie.Component.Space',                    'TEXT',     3),
    ('c78c9c36-d89a-4ee2-8040-0ca48ab3dcd1', 'COBie.Component.Length',                   'LENGTH',   3),
    ('d047f844-9187-4682-86ae-7deae256b2e8', 'COBie.Component.WarrantyStartDate',        'TEXT',     3),
    ('50740261-fc5c-42cb-b5cf-22bfcdae0d6d', 'COBie.Component.TagNumber',                'TEXT',     3),
    ('062ea58a-811b-46d0-b349-d78422566f37', 'COBie.Component.Name',                     'TEXT',     3),
    ('bbd6ef8a-38ad-447f-87ed-7860a898fc77', 'COBie.Component.BarCode',                  'TEXT',     3),
    ('929089af-bc2a-48a4-87f1-2c806908b2d6', 'COBie.Component.AssetIdentifier',          'TEXT',     3),
    ('633107f9-20e6-498a-ad57-f0923368e66c', 'COBie.Component.InstallationDate',         'TEXT',     3),
    ('9f4c93f0-6910-4963-a094-5361117ed743', 'COBie.Component.Area',                     'AREA',     3),
    ('337a60e5-9cd3-4c14-9c88-b75be7be2c49', 'COBie.Component.Description',              'TEXT',     3),

    # ── COBie.Facility (group 4) ───────────────────────────────────────────
    ('3040830c-fc22-4d95-9042-934226fb84a8', 'COBie.Facility.ProjectDescription',        'TEXT',     4),
    ('eefeb536-9529-452f-812c-88d9ab919659', 'COBie.Facility.SiteName',                  'TEXT',     4),
    ('e22df43a-6177-4820-b0dc-2f1f3b190e6a', 'COBie.Facility.Name',                      'TEXT',     4),
    ('256af546-68ad-42bd-9da0-a70888e70c8d', 'COBie.Facility.VolumeUnits',               'TEXT',     4),
    ('4785b851-cf4a-453b-8463-b748f7987875', 'COBie.Facility.AreaMeasurement',            'TEXT',     4),
    ('6b59cc9e-74c2-4fa3-a495-11bd806771d8', 'COBie.Facility.ProjectName',               'TEXT',     4),
    ('ec31719c-9346-4910-b601-b0c6cbc65b6f', 'COBie.Facility.LinearUnits',               'TEXT',     4),
    ('4ad7eaf8-720e-4964-83fc-1546f4f70610', 'COBie.Facility.Category',                  'TEXT',     4),
    ('4f0063fb-378e-4fbb-a30f-182c806a98cc', 'COBie.Facility.Phase',                     'TEXT',     4),
    ('fdbeeefd-61b7-423a-bc57-fb80ae15b134', 'COBie.Facility.SiteDescription',           'TEXT',     4),
    ('3f0f19e5-ee8e-48b7-887c-25672b18cffe', 'COBie.Facility.Description',               'TEXT',     4),
    ('25ca02e1-d8ae-4181-b6af-76e97789c5e0', 'COBie.Facility.CurrencyUnit',              'TEXT',     4),
    ('0b7217f2-8d95-4f6b-b985-aa5e129d1ac4', 'COBie.Facility.AreaUnits',                 'TEXT',     4),

    # ── COBie.Floor (group 5) ──────────────────────────────────────────────
    ('36b66e0e-b4bd-404a-9bf9-adbf05df6653', 'COBie.Floor.Elevation',                    'LENGTH',   5),
    ('f55eb371-aea9-4985-8fac-d0078bd1d627', 'COBie.Floor.Category',                     'TEXT',     5),
    ('c892c3cb-84a6-4d6d-a013-7f2f0acce337', 'COBie.Floor.Description',                  'TEXT',     5),
    ('bfe391d1-bca9-40bd-a73a-4d008d3600bf', 'COBie.Floor.Name',                         'TEXT',     5),
    ('6e2e6fd6-4088-48a0-b0ae-3be169d08e16', 'COBie.Floor.Height',                       'LENGTH',   5),

    # ── COBie.Space (group 6) ──────────────────────────────────────────────
    ('e0f1ef14-db3f-4b06-9e29-a310943f5a8f', 'COBie.Space.GrossArea',                    'AREA',     6),
    ('998a9b94-ff69-4f01-88d7-082f7fd8f792', 'COBie.Space.UsableHeight',                 'LENGTH',   6),
    ('69d876ab-2335-4297-a6bc-b2432ddf79fc', 'COBie.Space.RoomTag',                      'TEXT',     6),
    ('5d113dcf-733e-4a30-a056-47fa2da0acbd', 'COBie.Space.NetArea',                      'AREA',     6),
    ('b34230d4-b276-4f34-9c65-afe8c0bfa8c1', 'COBie.Space.Category',                     'TEXT',     6),
    ('4c30d8d5-081f-450d-973f-d2f3d9d144bc', 'COBie.Space.Description',                  'TEXT',     6),
    ('db5597d7-84ba-43e4-97f7-36066decd061', 'COBie.Space.Name',                         'TEXT',     6),

    # ── COBie.System (group 7) ─────────────────────────────────────────────
    ('b8e9d216-7a3c-4184-b094-e645268c4da6', 'COBie.System.Name',                        'TEXT',     7),
    ('ec6bdf8e-76e8-4e83-8ae9-2557c412a079', 'COBie.System.Description',                 'TEXT',     7),
    ('dc9005cd-3408-4f9e-b49d-9e8575928d1d', 'COBie.System.Category',                    'TEXT',     7),

    # ── COBie.Type (group 8) ───────────────────────────────────────────────
    ('48d7460a-ec9f-43a3-b051-6192aacf722a', 'COBie.Type.ReplacementCost',               'CURRENCY', 8),
    ('0b029313-5040-4cc0-9f53-6cd3ea6ae189', 'COBie.Type.WarrantyDurationParts',         'TEXT',     8),
    ('5486dd17-cd5d-4233-ae36-ac8f8965c838', 'COBie.Type.Size',                          'TEXT',     8),
    ('3ba1c328-0955-4f6c-9ab7-b873fa9edeb9', 'COBie.Type.Description',                   'TEXT',     8),
    ('af89e628-dddb-48d2-b7e2-0c43a1caf695', 'COBie.Type.CodePerformance',               'TEXT',     8),
    ('bd55d52a-207a-4d1e-a5e6-646e00f0e000', 'COBie.Type.ExpectedLife',                  'TEXT',     8),
    ('46ffbc2b-2ebe-414c-ad61-af8c8234eb8c', 'COBie.Type.Grade',                         'TEXT',     8),
    ('ca1c1731-b3c4-4c35-a9fe-06cf78d28270', 'COBie.Type.WarrantyGuarantorParts',        'TEXT',     8),
    ('5414df3b-cfb4-40f2-813c-a5c129c0c480', 'COBie.Type.Color',                         'TEXT',     8),
    ('16c06d3d-838a-4049-bafe-5484bc1c6815', 'COBie.Type.SustainabilityPerformance',     'TEXT',     8),
    ('7e853141-e2bc-4ed9-b67a-220429bb19ce', 'COBie.Type.WarrantyDurationUnit',          'TEXT',     8),
    ('c62f2c43-d4cc-4584-97c7-1b93631821c4', 'COBie.Type.Manufacturer',                  'TEXT',     8),
    ('caa9614f-7d1f-4b17-a17f-afd8e32c4fa8', 'COBie.Type.NominalHeight',                 'LENGTH',   8),
    ('5e233065-a501-4b75-befd-73ae95e29807', 'COBie.Type.WarrantyGuarantorLabor',        'TEXT',     8),
    ('dcc3dc6b-e03d-40cc-ba11-9fc195ff6b00', 'COBie.Type.Name',                          'TEXT',     8),
    ('a7d6726f-8690-45fb-8f3c-dd780afc494f', 'COBie.Type.Shape',                         'TEXT',     8),
    ('2b53b174-9fda-4289-9afd-acce150c61ea', 'COBie.Type.ModelNumber',                   'TEXT',     8),
    ('e566bc7c-7f7e-4539-97a9-224e53aa485d', 'AssetTypeMoveable',                        'YESNO',    8),
    ('e6b55f84-7e43-4ed3-8670-025ea5470ea9', 'COBie.Type.WarrantyDurationLabor',         'TEXT',     8),
    ('8bea5d8e-7168-416e-af6e-28282a95ace1', 'COBie.Type.WarrantyDescription',           'TEXT',     8),
    ('ec4d89ad-ea93-48a9-a316-a4dd30008dbe', 'COBie.Type.Features',                      'TEXT',     8),
    ('1691beae-d724-4a70-b6f6-7abd114e9dda', 'COBie.Type',                               'YESNO',    8),
    ('a9c784b7-821d-48b2-9762-c0095c21175e', 'COBie.Type.Category',                      'TEXT',     8),
    ('3eae11c6-307f-43b0-b531-bb1bb36c9d2b', 'COBie.Type.Length',                        'LENGTH',   8),
    ('801d88c6-ece7-4adc-873b-ff124dc0bdd1', 'COBie.Type.AccessibilityPerformance',      'TEXT',     8),
    ('bb9e03c7-88da-41d3-bf7a-6eecde3fc96e', 'COBie.Type.ModelReference',                'TEXT',     8),
    ('3303f7c7-2794-497c-9def-9e9dffb04a8d', 'COBie.Type.CreatedOn',                     'TEXT',     8),
    ('07070fc8-cebf-4526-be91-a23ffc60d11c', 'COBie.Type.AssetType',                     'TEXT',     8),
    ('10379ec8-1116-4691-8ee6-5613c37bc09a', 'COBie.Type.ExternalIdentifier',            'TEXT',     8),
    ('8c2253a5-2cca-464a-8333-931ec0f901a9', 'COBie.Type.CreatedBy',                     'TEXT',     8),
    ('a2c6cddc-fb59-41ca-8181-35d4a9891b07', 'COBie.Type.NominalLength',                 'LENGTH',   8),
    ('bee6f6de-2bf7-461a-9674-13bf26b8d77e', 'COBie.Type.Material',                      'TEXT',     8),
    ('cc970df4-7803-4137-821f-67097616cab2', 'COBie.Type.DurationUnit',                  'TEXT',     8),
    ('6c276cf6-7322-4358-8ca4-ec6ba087a054', 'COBie.Type.Constituents',                  'TEXT',     8),
    ('782e69f8-f233-4f32-aaf5-d32f051be5c9', 'COBie.Type.Area',                          'AREA',     8),
    ('941e36f0-8489-4b4b-83c4-8627d34b3e7e', 'COBie.Type.Finish',                        'TEXT',     8),
    ('e38edaff-5c38-40fa-91f7-f706c026d4d6', 'COBie.Type.NominalWidth',                  'LENGTH',   8),

    # ── COBie.Zone (group 9) ───────────────────────────────────────────────
    ('058451a5-0cec-47a8-8c0b-cc396b719e95', 'COBie.Zone.Category',                      'TEXT',     9),
]

# ---------------------------------------------------------------------------
# Build indexed dicts
# ---------------------------------------------------------------------------

PARAMS = {
    name: {
        'name':     name,
        'guid':     guid,
        'datatype': datatype,
        'group_id': group_id,
        'group':    _GROUPS[group_id],
    }
    for guid, name, datatype, group_id in _RAW
}

# Keyed by GUID string (lowercase, hyphenated) for fast reverse lookup
BY_GUID = {
    guid: PARAMS[name]
    for guid, name, _dt, _gid in _RAW
    for _ in [None]   # one-liner trick to avoid repeating _RAW tuple
}
# Simpler rebuild to avoid the trick above
BY_GUID = {entry['guid']: entry for entry in PARAMS.values()}

# ---------------------------------------------------------------------------
# AIR-specified Facility parameters that must be present and non-empty
#
# Maps full shared-parameter name -> GUID (for reliable Revit API lookup).
# Note: the original AIR spec used short aliases; these are the canonical
# names as defined in the shared parameter file.
#
#   AIR alias            -> Shared parameter name
#   SiteName             -> COBie.Facility.SiteName
#   Category             -> COBie.Facility.Category
#   ProjectName          -> COBie.Facility.ProjectName
#   Phase                -> COBie.Facility.Phase
#   BuildingDescription  -> COBie.Facility.Description
#   ProjectDescription   -> COBie.Facility.ProjectDescription
#   SiteDescription      -> COBie.Facility.SiteDescription
# ---------------------------------------------------------------------------

FACILITY_REQUIRED = [
    'COBie.Facility.SiteName',
    'COBie.Facility.Category',
    'COBie.Facility.ProjectName',
    'COBie.Facility.Phase',
    'COBie.Facility.Description',        # AIR: BuildingDescription
    'COBie.Facility.ProjectDescription',
    'COBie.Facility.SiteDescription',
]


def guid_for(param_name):
    """Return the GUID string for a parameter name, or None if not found."""
    entry = PARAMS.get(param_name)
    return entry['guid'] if entry else None
