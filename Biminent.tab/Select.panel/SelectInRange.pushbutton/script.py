# -*- coding: utf-8 -*-
__title__   = "Select in\nRange"
__doc__     = """Select elements whose instance parameter falls in a range.

Pick a category (All Categories by default) and one of its instance
parameters, then constrain it:

  - Text parameters (incl. Level, which shows its level name) match either an
    exact value or an alphanumeric range - everything from one value up to
    another, compared alphabetically, e.g. Level 01 to Level 05.
  - Numeric parameters take a from/to range in the project's display units,
    e.g. Area from 3.0 to 8.0. Either bound can be left blank for an
    open-ended range. The current data range is shown as a hint.

Select replaces the current selection with the matches and closes.

Part of Biminent Tools - biminent.com"""
__author__  = "Biminent"
__helpurl__ = "https://biminent.com"

import os

from pyrevit import revit
from Autodesk.Revit.DB import (
    CategoryType,
    ElementId,
    FilteredElementCollector,
    StorageType,
    UnitUtils,
)
from System.Collections.Generic import List

from biminent.ui import BiminentWindow

doc = revit.doc
uidoc = revit.uidoc

KIND_TEXT = "text"
KIND_NUMBER = "number"


# ---- units (version-compatible) --------------------------------------------

def _display_from_internal(param, internal):
    """Convert an internal-units double to the parameter's project display
    units. Falls back to the raw value if units can't be resolved."""
    try:
        return UnitUtils.ConvertFromInternalUnits(internal, param.GetUnitTypeId())
    except Exception:
        pass
    try:
        return UnitUtils.ConvertFromInternalUnits(internal, param.DisplayUnitType)
    except Exception:
        return internal


def _internal_from_display(param, display):
    try:
        return UnitUtils.ConvertToInternalUnits(display, param.GetUnitTypeId())
    except Exception:
        pass
    try:
        return UnitUtils.ConvertToInternalUnits(display, param.DisplayUnitType)
    except Exception:
        return display


def _unit_label(param):
    try:
        from Autodesk.Revit.DB import LabelUtils
        return LabelUtils.GetLabelForUnit(param.GetUnitTypeId())
    except Exception:
        pass
    try:
        from Autodesk.Revit.DB import LabelUtils
        return LabelUtils.GetLabelForUnit(param.DisplayUnitType)
    except Exception:
        return ""


# ---- parameter value reads -------------------------------------------------

def _param_kind(storage_type):
    if storage_type in (StorageType.String, StorageType.ElementId):
        return KIND_TEXT
    if storage_type in (StorageType.Integer, StorageType.Double):
        return KIND_NUMBER
    return None


def _text_value(param):
    """Comparable text of a text-like parameter (String -> its string,
    ElementId -> the referenced element's name via the value string)."""
    if param is None or not param.HasValue:
        return None
    try:
        if param.StorageType == StorageType.String:
            return param.AsString()
        return param.AsValueString()
    except Exception:
        return None


def _number_value(param):
    """Internal-units number of a numeric parameter, or None."""
    if param is None or not param.HasValue:
        return None
    try:
        if param.StorageType == StorageType.Double:
            return param.AsDouble()
        if param.StorageType == StorageType.Integer:
            return float(param.AsInteger())
    except Exception:
        return None
    return None


def _parse_float(text):
    text = (text or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return "ERR"


# ---- items -----------------------------------------------------------------

class CatItem(object):
    def __init__(self, label, category_id):
        self.Label = label
        self.category_id = category_id  # None == all categories


class ParamItem(object):
    def __init__(self, name, storage_type, sample_param):
        self.name = name
        self.storage_type = storage_type
        self.kind = _param_kind(storage_type)
        self.sample_param = sample_param  # a live Parameter for unit info
        self.Label = name


def _collect_categories():
    items = [CatItem("All Categories", None)]
    for cat in doc.Settings.Categories:
        try:
            if cat.CategoryType != CategoryType.Model or not cat.IsVisibleInUI:
                continue
        except Exception:
            continue
        items.append(CatItem(cat.Name, cat.Id))
    head, tail = items[0], sorted(items[1:], key=lambda i: i.Label.lower())
    return [head] + tail


# ---- window ----------------------------------------------------------------

class SelectInRangeWindow(BiminentWindow):
    def __init__(self):
        xaml = os.path.join(os.path.dirname(__file__), "SelectInRangeWindow.xaml")
        self._cats = _collect_categories()
        self._params = []
        self._loading = True
        BiminentWindow.__init__(self, xaml)
        self.cb_category.ItemsSource = self._cats
        self.cb_category.SelectedIndex = 0  # All Categories
        self._loading = False
        self._scan_params()

    # -- collectors --

    def _model_collector(self, category_id):
        col = FilteredElementCollector(doc).WhereElementIsNotElementType()
        if category_id is not None:
            col = col.OfCategoryId(category_id)
        return col

    def _scoped_collector(self):
        item = self.cb_category.SelectedItem
        category_id = item.category_id if item is not None else None
        if self.rb_view.IsChecked:
            col = FilteredElementCollector(doc, doc.ActiveView.Id).WhereElementIsNotElementType()
        else:
            col = FilteredElementCollector(doc).WhereElementIsNotElementType()
        if category_id is not None:
            col = col.OfCategoryId(category_id)
        return col

    # -- parameter discovery --

    def _scan_params(self):
        item = self.cb_category.SelectedItem
        if item is None:
            return
        self.set_status("Scanning parameters...")
        infos = {}
        try:
            for el in self._model_collector(item.category_id):
                try:
                    params = el.Parameters
                except Exception:
                    continue
                for p in params:
                    try:
                        st = p.StorageType
                        if _param_kind(st) is None:
                            continue
                        name = p.Definition.Name
                    except Exception:
                        continue
                    if name not in infos:
                        infos[name] = ParamItem(name, st, p)
        except Exception:
            self.report_exception("Select in Range")
            return

        self._params = sorted(infos.values(), key=lambda i: i.name.lower())
        self.cb_param.ItemsSource = None
        self.cb_param.ItemsSource = self._params
        if self._params:
            self.cb_param.SelectedIndex = 0
            self.set_status("{} parameter(s) found.".format(len(self._params)))
        else:
            self._show_panel(None)
            self.set_status("No usable parameters for this category.")
        self._validate()

    # -- ui state --

    def _show_panel(self, kind):
        from System.Windows import Visibility
        self.panel_text.Visibility = Visibility.Visible if kind == KIND_TEXT else Visibility.Collapsed
        self.panel_number.Visibility = Visibility.Visible if kind == KIND_NUMBER else Visibility.Collapsed

    def _current_param(self):
        return self.cb_param.SelectedItem

    def _prefill_number(self, item):
        """Show the data's current min/max for the chosen numeric parameter, in
        project units, and prefill the inputs as a starting range."""
        self.lbl_unit.Text = _unit_label(item.sample_param)
        lo = hi = None
        for el in self._model_collector(self.cb_category.SelectedItem.category_id):
            v = _number_value(el.LookupParameter(item.name))
            if v is None:
                continue
            lo = v if lo is None else min(lo, v)
            hi = v if hi is None else max(hi, v)
        if lo is None:
            self.tb_from_num.Text = ""
            self.tb_to_num.Text = ""
            self.lbl_range_hint.Text = "No values found for this parameter."
            return
        d_lo = _display_from_internal(item.sample_param, lo)
        d_hi = _display_from_internal(item.sample_param, hi)
        self.tb_from_num.Text = "{:.4g}".format(d_lo)
        self.tb_to_num.Text = "{:.4g}".format(d_hi)
        self.lbl_range_hint.Text = "Data range: {:.4g} to {:.4g} {}".format(
            d_lo, d_hi, self.lbl_unit.Text)

    # -- events --

    def category_changed(self, sender, e):
        if self._loading:
            return
        self._scan_params()

    def param_changed(self, sender, e):
        item = self._current_param()
        if item is None:
            self._show_panel(None)
            self._validate()
            return
        self._show_panel(item.kind)
        if item.kind == KIND_TEXT:
            self.tb_exact.Text = ""
            self.tb_from_text.Text = ""
            self.tb_to_text.Text = ""
            self._update_text_subpanels()
        elif item.kind == KIND_NUMBER:
            self._prefill_number(item)
        self._validate()

    def text_mode_changed(self, sender, e):
        if not self.IsLoaded:
            return
        self._update_text_subpanels()
        self._validate()

    def _update_text_subpanels(self):
        from System.Windows import Visibility
        exact = bool(self.rb_exact.IsChecked)
        self.sub_exact.Visibility = Visibility.Visible if exact else Visibility.Collapsed
        self.sub_textrange.Visibility = Visibility.Collapsed if exact else Visibility.Visible

    def input_changed(self, sender, e):
        if not self.IsLoaded:
            return
        self._validate()

    def _validate(self):
        item = self._current_param()
        if item is None:
            self.btn_select.IsEnabled = False
            return
        ok = False
        if item.kind == KIND_TEXT:
            if self.rb_exact.IsChecked:
                ok = bool(self.tb_exact.Text.strip())
            else:
                ok = bool(self.tb_from_text.Text.strip() or self.tb_to_text.Text.strip())
        elif item.kind == KIND_NUMBER:
            lo = _parse_float(self.tb_from_num.Text)
            hi = _parse_float(self.tb_to_num.Text)
            if lo == "ERR" or hi == "ERR":
                self.set_status("Enter numbers only for the range bounds.")
                self.btn_select.IsEnabled = False
                return
            ok = lo is not None or hi is not None
        self.btn_select.IsEnabled = ok
        if ok and self.status_text.Text.startswith("Enter"):
            self.set_status("")

    # -- select --

    def _matches_text(self, item):
        results = []
        if self.rb_exact.IsChecked:
            target = self.tb_exact.Text.strip().lower()
            for el in self._scoped_collector():
                v = _text_value(el.LookupParameter(item.name))
                if v is not None and v.strip().lower() == target:
                    results.append(el.Id)
            return results
        lo = self.tb_from_text.Text.strip().lower() or None
        hi = self.tb_to_text.Text.strip().lower() or None
        for el in self._scoped_collector():
            v = _text_value(el.LookupParameter(item.name))
            if v is None:
                continue
            k = v.strip().lower()
            if lo is not None and k < lo:
                continue
            if hi is not None and k > hi:
                continue
            results.append(el.Id)
        return results

    def _matches_number(self, item):
        lo_disp = _parse_float(self.tb_from_num.Text)
        hi_disp = _parse_float(self.tb_to_num.Text)
        lo = None if lo_disp in (None, "ERR") else _internal_from_display(item.sample_param, lo_disp)
        hi = None if hi_disp in (None, "ERR") else _internal_from_display(item.sample_param, hi_disp)
        # tolerance so a value equal to a bound is reliably included
        eps = 1e-9
        results = []
        for el in self._scoped_collector():
            v = _number_value(el.LookupParameter(item.name))
            if v is None:
                continue
            if lo is not None and v < lo - eps:
                continue
            if hi is not None and v > hi + eps:
                continue
            results.append(el.Id)
        return results

    def do_select(self, sender, e):
        item = self._current_param()
        if item is None:
            return
        self.set_status("Searching...")
        with self.report_errors("Select in Range"):
            if item.kind == KIND_TEXT:
                match_ids = self._matches_text(item)
            else:
                match_ids = self._matches_number(item)

            if not match_ids:
                self.set_status("No elements match that range.")
                return
            ids = List[ElementId]()
            for eid in match_ids:
                ids.Add(eid)
            uidoc.Selection.SetElementIds(ids)
            self.Close()


if __name__ == "__main__":
    # Modal: keeps every Revit API call inside the command's API context.
    SelectInRangeWindow().ShowDialog()
