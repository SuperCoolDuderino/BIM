# -*- coding: utf-8 -*-
"""
COBie Corrections — Validate & Correct
---------------------------------------
PyRevit pushbutton script for Revit 2022.

Workflow
--------
1. Collect all FamilySymbol elements + ProjectInformation from the active doc.
2. Validate them against COBie rules (cobie_rules.py via cobie_collector.py).
3. Display results in a WPF form grouped by COBie category with checkboxes.
4. Write confirmed corrections in a single named transaction (cobie_writer.py),
   OR simulate without writing when Dry Run is active.
5. Show a summary dialog (labelled accordingly for dry-run vs write mode).

Toolbar extras
--------------
- Dry Run checkbox  — simulate corrections; logs to pyRevit output panel
- Export CSV button — dump all collected issues to a CSV for offline review
- Undo reminder     — visible in write mode; hidden in dry-run mode
"""

import os
import sys
import clr

# ── pyRevit / Revit API ──────────────────────────────────────────────────────
from pyrevit import script, revit, forms
from pyrevit.revit import doc as ACTIVE_DOC

# ── Ensure the extension lib/ folder is on the path ─────────────────────────
_SCRIPT_DIR = os.path.dirname(__file__)                          # pushbutton/
_LIB_DIR    = os.path.join(_SCRIPT_DIR, '..', '..', '..', 'lib')
_LIB_DIR    = os.path.normpath(_LIB_DIR)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from cobie_collector import collect_issues
from cobie_writer    import apply_corrections, export_csv

# ── WPF / .NET ───────────────────────────────────────────────────────────────
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')
clr.AddReference('WindowsBase')

from System.Windows             import Window, Thickness, HorizontalAlignment, VerticalAlignment, Visibility, GridLength, GridUnitType
from System.Windows             import FontWeights, TextTrimming, CornerRadius
from System.Windows.Controls    import (
    ScrollViewer, StackPanel, Grid, ColumnDefinition, RowDefinition,
    CheckBox, TextBlock, Button, Border, ItemsControl, Label,
)
from System.Windows.Input       import Cursors
from System.Windows.Media       import SolidColorBrush, Color
from System.Windows.Markup      import XamlReader
from System.IO                  import File

# ── Colours ──────────────────────────────────────────────────────────────────
_C_HEADER_BG  = SolidColorBrush(Color.FromRgb(226, 234, 243))   # #E2EAF3
_C_WHITE      = SolidColorBrush(Color.FromRgb(255, 255, 255))
_C_RULE_FG    = SolidColorBrush(Color.FromRgb(160, 100,  40))   # amber
_C_ERROR_FG   = SolidColorBrush(Color.FromRgb(180,  30,  30))
_C_MUTED_FG   = SolidColorBrush(Color.FromRgb( 90,  90,  90))

# ── Logger ───────────────────────────────────────────────────────────────────
logger = script.get_logger()

# ────────────────────────────────────────────────────────────────────────────
# WPF window builder
# ────────────────────────────────────────────────────────────────────────────

_XAML_PATH = os.path.join(_LIB_DIR, 'ui_form.xaml')


def _load_window():
    """Load the XAML shell and return the Window object."""
    xaml_text = File.ReadAllText(_XAML_PATH)
    return XamlReader.Parse(xaml_text)


def _make_thickness(*args):
    """Convenience: Thickness(left,top,right,bottom) or single value."""
    if len(args) == 1:
        return Thickness(args[0])
    return Thickness(*args)


def _text(txt, foreground=None, bold=False, margin=None):
    tb = TextBlock()
    tb.Text = txt
    if foreground:
        tb.Foreground = foreground
    if bold:
        tb.FontWeight = FontWeights.SemiBold
    if margin:
        tb.Margin = margin
    tb.VerticalAlignment = VerticalAlignment.Center
    tb.TextTrimming = TextTrimming.CharacterEllipsis
    return tb


def _make_grid_col(width_star=None, width_px=None):
    cd = ColumnDefinition()
    if width_star is not None:
        cd.Width = GridLength(width_star, GridUnitType.Star)
    elif width_px is not None:
        cd.Width = GridLength(width_px, GridUnitType.Pixel)
    return cd


# ────────────────────────────────────────────────────────────────────────────
# Group panel builder
# ────────────────────────────────────────────────────────────────────────────

def _build_group_panel(group_name, issues, checkbox_store, on_checked_changed):
    """
    Build one group Border containing:
      - header row with group name + Select All / Deselect All buttons
      - column header row
      - one row per issue with checkbox, Was, Corrected To, Rule
    Returns the Border element.
    """
    outer = Border()
    outer.Margin      = _make_thickness(0, 0, 0, 12)
    outer.Background  = _C_WHITE
    outer.BorderBrush = SolidColorBrush(Color.FromRgb(208, 208, 208))
    outer.BorderThickness = _make_thickness(1)
    outer.CornerRadius = CornerRadius(4)

    sp = StackPanel()
    outer.Child = sp

    # ── Group header ────────────────────────────────────────────────────────
    hdr_border = Border()
    hdr_border.Background    = _C_HEADER_BG
    hdr_border.CornerRadius  = CornerRadius(4, 4, 0, 0)
    hdr_border.Padding       = _make_thickness(10, 6, 10, 6)

    hdr_grid = Grid()
    hdr_grid.ColumnDefinitions.Add(_make_grid_col(width_star=1))
    hdr_grid.ColumnDefinitions.Add(_make_grid_col(width_px=90))
    hdr_grid.ColumnDefinitions.Add(_make_grid_col(width_px=95))

    lbl = TextBlock()
    lbl.Text       = group_name
    lbl.FontWeight = FontWeights.SemiBold
    lbl.FontSize   = 14
    lbl.Foreground = SolidColorBrush(Color.FromRgb(26, 58, 92))
    lbl.VerticalAlignment = VerticalAlignment.Center
    Grid.SetColumn(lbl, 0)

    def _make_small_btn(txt, col, click_fn):
        btn = Button()
        btn.Content   = txt
        btn.Padding   = _make_thickness(8, 4, 8, 4)
        btn.Margin    = _make_thickness(0, 0, 6 if col == 1 else 0, 0)
        btn.Cursor    = Cursors.Hand
        btn.FontSize  = 11
        btn.Click    += click_fn
        Grid.SetColumn(btn, col)
        return btn

    # Capture group-local checkboxes list for the lambda closures
    group_cbs = []
    checkbox_store[group_name] = group_cbs

    def on_select_all(s, e):
        for cb in group_cbs:
            cb.IsChecked = True

    def on_deselect_all(s, e):
        for cb in group_cbs:
            cb.IsChecked = False

    btn_sel   = _make_small_btn('Select All',   1, on_select_all)
    btn_desel = _make_small_btn('Deselect All', 2, on_deselect_all)

    hdr_grid.Children.Add(lbl)
    hdr_grid.Children.Add(btn_sel)
    hdr_grid.Children.Add(btn_desel)
    hdr_border.Child = hdr_grid
    sp.Children.Add(hdr_border)

    # ── Column headers ───────────────────────────────────────────────────────
    col_hdr = Grid()
    col_hdr.Margin = _make_thickness(10, 6, 10, 2)
    col_hdr.ColumnDefinitions.Add(_make_grid_col(width_px=32))
    col_hdr.ColumnDefinitions.Add(_make_grid_col(width_star=1))
    col_hdr.ColumnDefinitions.Add(_make_grid_col(width_star=1))
    col_hdr.ColumnDefinitions.Add(_make_grid_col(width_px=120))

    for idx, txt in enumerate(['', 'Was', 'Corrected To', 'Rule']):
        tb = TextBlock()
        tb.Text       = txt
        tb.FontWeight = FontWeights.Bold
        tb.Foreground = _C_MUTED_FG
        tb.Margin     = _make_thickness(4, 0, 4, 0)
        Grid.SetColumn(tb, idx)
        col_hdr.Children.Add(tb)

    sp.Children.Add(col_hdr)

    # ── Issue rows ───────────────────────────────────────────────────────────
    for i, issue in enumerate(issues):
        row_bg = SolidColorBrush(
            Color.FromRgb(250, 250, 250) if i % 2 == 0
            else Color.FromRgb(239, 239, 239)
        )

        row_border = Border()
        row_border.Background = row_bg
        row_border.Padding    = _make_thickness(10, 3, 10, 3)

        row_grid = Grid()
        row_grid.ColumnDefinitions.Add(_make_grid_col(width_px=32))
        row_grid.ColumnDefinitions.Add(_make_grid_col(width_star=1))
        row_grid.ColumnDefinitions.Add(_make_grid_col(width_star=1))
        row_grid.ColumnDefinitions.Add(_make_grid_col(width_px=120))

        # Checkbox — disable if no corrected_to value
        cb = CheckBox()
        cb.VerticalAlignment = VerticalAlignment.Center
        no_fix = not (issue.get('corrected_to') or '').strip() or \
                 (issue.get('corrected_to') or '').startswith('<')
        cb.IsEnabled = not no_fix
        cb.IsChecked = not no_fix   # pre-check actionable items
        cb.Tag       = issue
        cb.Checked   += on_checked_changed
        cb.Unchecked += on_checked_changed
        group_cbs.append(cb)
        Grid.SetColumn(cb, 0)

        tb_was = _text(issue.get('was', ''), margin=_make_thickness(4, 0, 4, 0))
        Grid.SetColumn(tb_was, 1)

        corrected = issue.get('corrected_to') or '—'
        tb_corr = _text(
            corrected,
            foreground=_C_ERROR_FG if corrected.startswith('<') else None,
            margin=_make_thickness(4, 0, 4, 0)
        )
        Grid.SetColumn(tb_corr, 2)

        tb_rule = _text(
            issue.get('rule', ''),
            foreground=_C_RULE_FG,
            margin=_make_thickness(4, 0, 4, 0)
        )
        tb_rule.FontSize = 11
        Grid.SetColumn(tb_rule, 3)

        row_grid.Children.Add(cb)
        row_grid.Children.Add(tb_was)
        row_grid.Children.Add(tb_corr)
        row_grid.Children.Add(tb_rule)
        row_border.Child = row_grid
        sp.Children.Add(row_border)

    return outer


# ────────────────────────────────────────────────────────────────────────────
# Main entry point
# ────────────────────────────────────────────────────────────────────────────

def main():
    doc = ACTIVE_DOC

    # ── Collect ─────────────────────────────────────────────────────────────
    with forms.ProgressBar(title='COBie — Collecting issues…', cancellable=False):
        try:
            issues = collect_issues(doc)
        except Exception as exc:
            forms.alert(
                'Collection failed:\n{}'.format(exc),
                title='COBie Error', warn_icon=True
            )
            return

    if not issues:
        forms.alert(
            'No COBie compliance issues found in this model.',
            title='COBie Corrections'
        )
        return

    # ── Group ────────────────────────────────────────────────────────────────
    groups = {}
    for issue in issues:
        cat = issue.get('category', 'Component')
        groups.setdefault(cat, []).append(issue)

    GROUP_ORDER = ['Facility', 'Floor', 'Type', 'Component']

    # ── Build WPF window ─────────────────────────────────────────────────────
    window = _load_window()

    groups_panel      = window.FindName('GroupsPanel')
    apply_btn         = window.FindName('ApplyButton')
    cancel_btn        = window.FindName('CancelButton')
    issue_count_label = window.FindName('IssueCountLabel')
    sel_feedback      = window.FindName('SelectionFeedback')
    dry_run_cb        = window.FindName('DryRunCheckbox')
    export_btn        = window.FindName('ExportCsvButton')
    undo_reminder     = window.FindName('UndoReminder')

    issue_count_label.Text = '({} issue{} found)'.format(
        len(issues), 's' if len(issues) != 1 else ''
    )

    checkbox_store = {}   # group_name -> [CheckBox, ...]

    def _update_apply_btn(sender=None, e=None):
        """Count checked+enabled items and refresh the Apply button state."""
        checked = sum(
            1
            for cbs in checkbox_store.values()
            for cb in cbs
            if cb.IsEnabled and cb.IsChecked
        )
        apply_btn.IsEnabled = checked > 0
        sel_feedback.Text   = '{} correction{} selected'.format(
            checked, 's' if checked != 1 else ''
        )

    # Populate groups
    for cat in GROUP_ORDER:
        if cat not in groups:
            continue
        panel = _build_group_panel(
            cat, groups[cat], checkbox_store, _update_apply_btn
        )
        groups_panel.Children.Add(panel)

    _update_apply_btn()

    # ── Dry Run toggle — updates button label and undo reminder visibility ───
    def _on_dry_run_toggled(sender=None, e=None):
        is_dry = bool(dry_run_cb.IsChecked)
        apply_btn.Content = 'Preview Changes' if is_dry else 'Apply Corrections'
        undo_reminder.Visibility = Visibility.Collapsed if is_dry else Visibility.Visible

    dry_run_cb.Checked   += _on_dry_run_toggled
    dry_run_cb.Unchecked += _on_dry_run_toggled

    # ── Export CSV — available at any time while the form is open ────────────
    def on_export_csv(sender, e):
        save_path = forms.save_file(
            file_ext='csv',
            default_name='COBie_Validation_Results.csv',
            title='Export COBie Validation Results'
        )
        if not save_path:
            return   # user cancelled
        try:
            export_csv(issues, save_path)
            forms.alert(
                'Exported {} issue{} to:\n{}'.format(
                    len(issues), 's' if len(issues) != 1 else '', save_path
                ),
                title='COBie — Export Complete'
            )
        except Exception as exc:
            forms.alert(
                'Export failed:\n{}'.format(exc),
                title='COBie Error', warn_icon=True
            )

    export_btn.Click += on_export_csv

    # ── Apply / Preview ──────────────────────────────────────────────────────
    result_holder = {'confirmed': None, 'dry_run': False}

    def on_apply(sender, e):
        confirmed = [
            cb.Tag
            for cbs in checkbox_store.values()
            for cb in cbs
            if cb.IsEnabled and cb.IsChecked
        ]
        result_holder['confirmed'] = confirmed
        result_holder['dry_run']   = bool(dry_run_cb.IsChecked)
        window.DialogResult = True
        window.Close()

    def on_cancel(sender, e):
        window.DialogResult = False
        window.Close()

    apply_btn.Click  += on_apply
    cancel_btn.Click += on_cancel

    # ── Show ─────────────────────────────────────────────────────────────────
    window.ShowDialog()

    confirmed  = result_holder['confirmed']
    is_dry_run = result_holder['dry_run']

    if not confirmed:
        return   # user cancelled or nothing checked

    # ── Write / Simulate ─────────────────────────────────────────────────────
    try:
        summary = apply_corrections(doc, confirmed, dry_run=is_dry_run)
    except Exception as exc:
        forms.alert(
            'Corrections failed (transaction rolled back):\n{}'.format(exc),
            title='COBie Error', warn_icon=True
        )
        return

    # ── Summary ──────────────────────────────────────────────────────────────
    if is_dry_run:
        title  = 'COBie — Dry Run Preview'
        header = '[DRY RUN — no changes written to the model]'
        applied_label = '  Would apply : {}'.format(summary['applied'])
    else:
        title  = 'COBie — Summary'
        header = 'COBie Corrections complete.'
        applied_label = '  Applied : {}'.format(summary['applied'])

    lines = [
        header,
        '',
        applied_label,
        '  Skipped  : {}'.format(summary['skipped']),
        '  Failed   : {}'.format(len(summary['failed'])),
    ]
    if summary['failed']:
        lines += ['', 'Details:'] + ['  \u2022 ' + f for f in summary['failed']]

    forms.alert('\n'.join(lines), title=title)


# ── pyRevit calls __revit__ implicitly; just run main() ─────────────────────
main()
