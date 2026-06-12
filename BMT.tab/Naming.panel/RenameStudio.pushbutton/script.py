# -*- coding: utf-8 -*-
__title__   = "Rename\nStudio"
__doc__     = """Batch rename almost anything: Views, Sheets, Levels, Grids,
Rooms, Areas, Spaces, Materials, Families, Types, Groups, Worksets, Phases,
Scope Boxes, Reference Planes, Line Styles and View Filters.

Find & replace with live preview, plus prefix and suffix.
Check the elements you want, see the result before you commit.
Choose which categories appear in the dropdown via the settings (gear) button.

Part of Biminent Tools - biminent.com"""
__author__  = "Biminent"
__helpurl__ = "https://biminent.com"

import os

from pyrevit import revit
from System.Windows import Visibility

from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    ElementType,
    Family,
    FilteredElementCollector,
    FilteredWorksetCollector,
    Grid,
    GroupType,
    Level,
    Material,
    ParameterFilterElement,
    Phase,
    ReferencePlane,
    Transaction,
    View,
    ViewSheet,
    WorksetKind,
    WorksetTable,
)

from biminent import config
from biminent.ui import BiminentWindow

doc = revit.doc

TOOL_CONFIG = "rename_studio"


class RenameItem(object):
    """One renamable element with its preview state."""

    def __init__(self, element, old_name):
        self.element = element
        self.checked = True
        self.manual = False  # True once the user typed the new name directly
        self.OldName = old_name
        self.NewName = old_name

    def is_pending(self):
        return self.checked and self.NewName and self.NewName != self.OldName


# ---- scopes ---------------------------------------------------------------
# Each scope: (label, collect(doc) -> [RenameItem], apply(element, new_name))

def _set_name(element, new_name):
    element.Name = new_name


def _collect_views(doc):
    items = []
    for v in FilteredElementCollector(doc).OfClass(View):
        if v.IsTemplate or isinstance(v, ViewSheet):
            continue
        name = v.Name
        if name.startswith("<"):  # internal views, e.g. <Revision Schedule>
            continue
        items.append(RenameItem(v, name))
    return items


def _collect_view_templates(doc):
    return [RenameItem(v, v.Name)
            for v in FilteredElementCollector(doc).OfClass(View)
            if v.IsTemplate]


def _collect_sheet_names(doc):
    return [RenameItem(s, s.Name)
            for s in FilteredElementCollector(doc).OfClass(ViewSheet)]


def _collect_sheet_numbers(doc):
    return [RenameItem(s, s.SheetNumber)
            for s in FilteredElementCollector(doc).OfClass(ViewSheet)]


def _set_sheet_number(sheet, new_number):
    sheet.SheetNumber = new_number


def _collect_levels(doc):
    return [RenameItem(l, l.Name)
            for l in FilteredElementCollector(doc).OfClass(Level)]


def _collect_grids(doc):
    return [RenameItem(g, g.Name)
            for g in FilteredElementCollector(doc).OfClass(Grid)]


def _collect_rooms(doc):
    items = []
    collector = FilteredElementCollector(doc) \
        .OfCategory(BuiltInCategory.OST_Rooms) \
        .WhereElementIsNotElementType()
    for r in collector:
        param = r.get_Parameter(BuiltInParameter.ROOM_NAME)
        if param:
            items.append(RenameItem(r, param.AsString() or ""))
    return items


def _set_room_name(room, new_name):
    room.get_Parameter(BuiltInParameter.ROOM_NAME).Set(new_name)


def _collect_materials(doc):
    return [RenameItem(m, m.Name)
            for m in FilteredElementCollector(doc).OfClass(Material)]


def _collect_filters(doc):
    return [RenameItem(f, f.Name)
            for f in FilteredElementCollector(doc).OfClass(ParameterFilterElement)]


def _collect_families(doc):
    return [RenameItem(f, f.Name)
            for f in FilteredElementCollector(doc).OfClass(Family)]


def _collect_types(doc):
    items = []
    for t in FilteredElementCollector(doc).OfClass(ElementType):
        name = t.Name
        if name:
            items.append(RenameItem(t, name))
    return items


def _collect_groups(doc):
    return [RenameItem(g, g.Name)
            for g in FilteredElementCollector(doc).OfClass(GroupType)]


def _collect_areas(doc):
    items = []
    collector = FilteredElementCollector(doc) \
        .OfCategory(BuiltInCategory.OST_Areas) \
        .WhereElementIsNotElementType()
    for a in collector:
        param = a.get_Parameter(BuiltInParameter.ROOM_NAME)
        if param:
            items.append(RenameItem(a, param.AsString() or ""))
    return items


def _collect_spaces(doc):
    items = []
    collector = FilteredElementCollector(doc) \
        .OfCategory(BuiltInCategory.OST_MEPSpaces) \
        .WhereElementIsNotElementType()
    for s in collector:
        param = s.get_Parameter(BuiltInParameter.ROOM_NAME)
        if param:
            items.append(RenameItem(s, param.AsString() or ""))
    return items


def _collect_worksets(doc):
    if not doc.IsWorkshared:
        return []
    return [RenameItem(w, w.Name)
            for w in FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset)]


def _rename_workset(workset, new_name):
    WorksetTable.RenameWorkset(doc, workset.Id, new_name)


def _collect_phases(doc):
    return [RenameItem(p, p.Name)
            for p in FilteredElementCollector(doc).OfClass(Phase)]


def _collect_scope_boxes(doc):
    collector = FilteredElementCollector(doc) \
        .OfCategory(BuiltInCategory.OST_VolumeOfInterest) \
        .WhereElementIsNotElementType()
    return [RenameItem(b, b.Name) for b in collector]


def _collect_reference_planes(doc):
    items = []
    for rp in FilteredElementCollector(doc).OfClass(ReferencePlane):
        if rp.Name and rp.Name != "Reference Plane":  # skip unnamed defaults
            items.append(RenameItem(rp, rp.Name))
    return items


def _collect_line_styles(doc):
    items = []
    lines = doc.Settings.Categories.get_Item(BuiltInCategory.OST_Lines)
    if lines:
        for sub in lines.SubCategories:
            items.append(RenameItem(sub, sub.Name))
    return items


def _set_category_name(category, new_name):
    category.Name = new_name


# (label, collect, apply, group) - grouped by domain, ordered most-used first.
SCOPES = [
    ("Views",            _collect_views,            _set_name,         "Views & Sheets"),
    ("View Templates",   _collect_view_templates,   _set_name,         "Views & Sheets"),
    ("View Filters",     _collect_filters,          _set_name,         "Views & Sheets"),
    ("Sheets (Name)",    _collect_sheet_names,      _set_name,         "Views & Sheets"),
    ("Sheets (Number)",  _collect_sheet_numbers,    _set_sheet_number, "Views & Sheets"),

    ("Levels",           _collect_levels,           _set_name,         "Datums & References"),
    ("Grids",            _collect_grids,            _set_name,         "Datums & References"),
    ("Reference Planes", _collect_reference_planes, _set_name,         "Datums & References"),
    ("Scope Boxes",      _collect_scope_boxes,      _set_name,         "Datums & References"),

    ("Rooms",            _collect_rooms,            _set_room_name,    "Spaces"),
    ("Areas",            _collect_areas,            _set_room_name,    "Spaces"),
    ("Spaces (MEP)",     _collect_spaces,           _set_room_name,    "Spaces"),

    ("Families",         _collect_families,         _set_name,         "Components"),
    ("Types (All)",      _collect_types,            _set_name,         "Components"),
    ("Groups",           _collect_groups,           _set_name,         "Components"),
    ("Materials",        _collect_materials,        _set_name,         "Components"),
    ("Line Styles",      _collect_line_styles,      _set_category_name, "Components"),

    ("Worksets",         _collect_worksets,         _rename_workset,   "Project"),
    ("Phases",           _collect_phases,           _set_name,         "Project"),
]


ALL_SCOPE_LABELS = [s[0] for s in SCOPES]
SCOPE_BY_LABEL = dict((s[0], s) for s in SCOPES)

# Shown out of the box; the rest of the catalog is enabled via settings.
DEFAULT_LABELS = [
    "Views", "View Templates", "View Filters",
    "Sheets (Name)", "Sheets (Number)",
    "Levels", "Grids", "Rooms", "Materials",
]


def load_enabled_labels():
    """Category labels enabled in settings; falls back to the default set."""
    saved = (config.load(TOOL_CONFIG) or {}).get("categories")
    if not saved:
        return list(DEFAULT_LABELS)
    valid = [l for l in ALL_SCOPE_LABELS if l in saved]
    return valid or list(DEFAULT_LABELS)


# ---- settings window --------------------------------------------------------

class ScopeOption(object):
    def __init__(self, label, enabled):
        self.Label = label
        self.checked = enabled


class RenameSettingsWindow(BiminentWindow):
    def __init__(self, enabled_labels):
        xaml = os.path.join(os.path.dirname(__file__), "RenameSettingsWindow.xaml")
        BiminentWindow.__init__(self, xaml)
        self.saved = False
        self._options = [ScopeOption(label, label in enabled_labels)
                         for label in sorted(ALL_SCOPE_LABELS)]
        self.list_scopes.ItemsSource = self._options

    def enabled_labels(self):
        return [o.Label for o in self._options if o.checked]

    def option_checked(self, sender, e):
        option = sender.DataContext
        if option is None:
            return
        option.checked = True
        self.warning_text.Visibility = Visibility.Collapsed

    def option_unchecked(self, sender, e):
        option = sender.DataContext
        if option is None:
            return
        option.checked = False

    def do_save(self, sender, e):
        if not self.enabled_labels():
            self.warning_text.Visibility = Visibility.Visible
            return
        self.saved = True
        self.Close()


# ---- window ----------------------------------------------------------------

class RenameStudioWindow(BiminentWindow):
    def __init__(self):
        xaml = os.path.join(os.path.dirname(__file__), "RenameStudioWindow.xaml")
        self._items = []
        self._loading = True
        self._enabled_labels = load_enabled_labels()
        self._visible_scopes = []
        BiminentWindow.__init__(self, xaml)
        self._loading = False
        self._rebuild_scopes()

    # -- state ----------------------------------------------------------

    def _scope(self):
        label = self.cmb_scope.SelectedItem
        return SCOPE_BY_LABEL.get(label) if label else None

    def _rebuild_scopes(self):
        """Refill the category dropdown from the enabled labels (sorted
        alphabetically), keeping the current selection when it survives the
        settings change."""
        previous = self.cmb_scope.SelectedItem
        labels = sorted(s[0] for s in SCOPES if s[0] in self._enabled_labels)

        self._loading = True
        self.cmb_scope.Items.Clear()
        for label in labels:
            self.cmb_scope.Items.Add(label)
        self._loading = False

        index = labels.index(previous) if previous in labels else 0
        self.cmb_scope.SelectedIndex = index  # triggers scope_changed -> reload

    def _reload(self):
        scope = self._scope()
        if scope is None:
            return
        collect = scope[1]
        self._items = sorted(collect(doc), key=lambda i: i.OldName.lower())
        self._apply_rules()

    def _apply_rules(self):
        find = self.tb_find.Text or ""
        replace = self.tb_replace.Text or ""
        prefix = self.tb_prefix.Text or ""
        suffix = self.tb_suffix.Text or ""
        for item in self._items:
            if item.manual:
                continue  # user typed this name directly; rules don't touch it
            new = item.OldName.replace(find, replace) if find else item.OldName
            if prefix or suffix:
                new = prefix + new + suffix
            item.NewName = new
        self._refresh_list()

    def _visible_items(self):
        text = (self.tb_filter.Text or "").lower()
        if not text:
            return list(self._items)
        return [i for i in self._items if text in i.OldName.lower()]

    def _refresh_list(self):
        self.list_items.ItemsSource = None
        self.list_items.ItemsSource = self._visible_items()
        self._refresh_counts()

    def _refresh_counts(self):
        checked = sum(1 for i in self._items if i.checked)
        pending = sum(1 for i in self._items if i.is_pending())
        self.lbl_count.Text = "{} of {} checked · {} will change".format(
            checked, len(self._items), pending)
        self.btn_rename.IsEnabled = pending > 0
        self.btn_rename.Content = "Rename ({})".format(pending) if pending else "Rename"

    # -- events ----------------------------------------------------------

    def scope_changed(self, sender, e):
        if self._loading or self.cmb_scope.SelectedIndex < 0:
            return
        self.status_text.Text = ""
        self._reload()

    def open_settings(self, sender, e):
        settings = RenameSettingsWindow(self._enabled_labels)
        settings.Owner = self
        settings.ShowDialog()
        if settings.saved:
            self._enabled_labels = settings.enabled_labels()
            config.save(TOOL_CONFIG, {"categories": self._enabled_labels})
            self._rebuild_scopes()

    def rules_changed(self, sender, e):
        if self._loading:
            return
        self._apply_rules()

    def filter_changed(self, sender, e):
        if self._loading:
            return
        self._refresh_list()

    def item_checked(self, sender, e):
        # DataContext is None while WPF detaches/recycles list rows
        # (e.g. when ItemsSource is reset) — those events are not user clicks.
        item = sender.DataContext
        if item is None:
            return
        item.checked = True
        self._refresh_counts()

    def item_unchecked(self, sender, e):
        item = sender.DataContext
        if item is None:
            return
        item.checked = False
        self._refresh_counts()

    def newname_edited(self, sender, e):
        # TextChanged also fires when WPF itself sets the text during row
        # creation/recycling — only a focused textbox means the user typed.
        item = sender.DataContext
        if item is None or not sender.IsKeyboardFocused:
            return
        item.NewName = sender.Text
        item.manual = True
        self._refresh_counts()

    def check_all(self, sender, e):
        for item in self._visible_items():
            item.checked = True
        self._refresh_list()

    def uncheck_all(self, sender, e):
        for item in self._visible_items():
            item.checked = False
        self._refresh_list()

    def do_rename(self, sender, e):
        scope = self._scope()
        if scope is None:
            return
        label, _, apply_name, _ = scope
        targets = [i for i in self._items if i.is_pending()]
        if not targets:
            return
        with self.report_errors("Rename"):
            done, skipped = 0, 0
            t = Transaction(doc, "Biminent · Rename {}".format(label))
            t.Start()
            try:
                for item in targets:
                    try:
                        apply_name(item.element, item.NewName)
                        done += 1
                    except Exception:
                        skipped += 1  # most often a duplicate-name conflict
                t.Commit()
            except Exception:
                t.RollBack()
                raise

            message = "Renamed {}".format(done)
            if skipped:
                message += " · {} skipped (name conflict)".format(skipped)
            self.set_status(message)
            self._reload()


if __name__ == "__main__":
    RenameStudioWindow().ShowDialog()
