# -*- coding: utf-8 -*-
import os

from pyrevit import revit
from Autodesk.Revit.DB import (
    ElementId,
    FilteredElementCollector,
    StorageType,
)
from System.Collections.Generic import List

from biminent.ui import BiminentWindow

doc = revit.doc
uidoc = revit.uidoc


# ---- parameter value keys --------------------------------------------------
# Two elements "match" on a parameter when their values produce the same key.

def _param_value_key(param):
    """A hashable key for a parameter's value, or None if it has no usable
    value. Same key == same value for matching purposes."""
    if param is None or not param.HasValue:
        return None
    st = param.StorageType
    try:
        if st == StorageType.String:
            return ("s", param.AsString())
        if st == StorageType.Integer:
            return ("i", param.AsInteger())
        if st == StorageType.Double:
            # round to swallow floating-point noise on identical values
            return ("d", round(param.AsDouble(), 9))
        if st == StorageType.ElementId:
            return ("e", param.AsElementId().IntegerValue)
    except Exception:
        return None
    return None


class ParamItem(object):
    """A selectable instance parameter of the seed element."""
    def __init__(self, name, value_label):
        self.name = name
        self.Label = name if not value_label else u"{}  =  {}".format(name, value_label)


def _instance_param_items(element):
    """Instance parameters of the seed that carry a comparable value, sorted by
    name. Read-only parameters are still fine to match on (e.g. Length)."""
    items = []
    seen = set()
    try:
        params = list(element.Parameters)
    except Exception:
        params = []
    for p in params:
        try:
            if _param_value_key(p) is None:
                continue
            name = p.Definition.Name
        except Exception:
            continue
        if name in seen:
            continue
        seen.add(name)
        try:
            value_label = p.AsValueString() or (
                p.AsString() if p.StorageType == StorageType.String else "")
        except Exception:
            value_label = ""
        items.append(ParamItem(name, value_label))
    return sorted(items, key=lambda i: i.name.lower())


# ---- candidate collection --------------------------------------------------

def _collector(in_view):
    if in_view:
        return FilteredElementCollector(doc, doc.ActiveView.Id)
    return FilteredElementCollector(doc)


def _element_family_name(element):
    """Family name of an element via its type, or None."""
    try:
        type_el = doc.GetElement(element.GetTypeId())
        if type_el is None:
            return None
        return type_el.FamilyName
    except Exception:
        return None


def _element_name(element):
    """Safe name read - Element.Name can fail to resolve on some types in
    IronPython, so fall back to the Name parameter then an empty string."""
    if element is None:
        return ""
    try:
        return element.Name or ""
    except Exception:
        pass
    try:
        from Autodesk.Revit.DB import Element
        return Element.Name.GetValue(element) or ""
    except Exception:
        return ""


# ---- window ----------------------------------------------------------------

class SelectSimilarWindow(BiminentWindow):
    def __init__(self, seed):
        xaml = os.path.join(os.path.dirname(__file__), "SelectSimilarWindow.xaml")
        self._seed = seed
        self._params = _instance_param_items(seed)
        BiminentWindow.__init__(self, xaml)

        cat_name = seed.Category.Name if seed.Category is not None else "(no category)"
        type_el = doc.GetElement(seed.GetTypeId())
        type_name = _element_name(type_el)
        self.lbl_seed.Text = u"{} \u00b7 {}".format(cat_name, type_name) if type_name else cat_name

        self.cb_param.ItemsSource = self._params
        if self._params:
            self.cb_param.SelectedIndex = 0
        else:
            self.rb_param.IsEnabled = False

    # -- mode --

    def mode_changed(self, sender, e):
        if not self.IsLoaded:
            return
        self.cb_param.IsEnabled = bool(self.rb_param.IsChecked) and bool(self._params)
        self._validate()

    def param_changed(self, sender, e):
        self._validate()

    def _validate(self):
        if self.rb_param.IsChecked and not self.cb_param.SelectedItem:
            self.btn_select.IsEnabled = False
            self.set_status("Pick a parameter to match on.")
        else:
            self.btn_select.IsEnabled = True
            self.set_status("")

    # -- select --

    def _matches(self):
        in_view = bool(self.rb_view.IsChecked)
        cat = self._seed.Category
        if cat is None:
            self.set_status("The picked element has no category.")
            return []
        cat_id = cat.Id

        base = (_collector(in_view)
                .OfCategoryId(cat_id)
                .WhereElementIsNotElementType())

        if self.rb_category.IsChecked:
            return list(base.ToElementIds())

        if self.rb_type.IsChecked:
            seed_type_id = self._seed.GetTypeId()
            return [el.Id for el in base.ToElements()
                    if el.GetTypeId() == seed_type_id]

        if self.rb_family.IsChecked:
            seed_family = _element_family_name(self._seed)
            return [el.Id for el in base.ToElements()
                    if _element_family_name(el) == seed_family]

        # Instance parameter value
        item = self.cb_param.SelectedItem
        if item is None:
            return []
        seed_key = _param_value_key(self._seed.LookupParameter(item.name))
        if seed_key is None:
            self.set_status("The seed has no value for that parameter.")
            return []
        matches = []
        for el in base.ToElements():
            if _param_value_key(el.LookupParameter(item.name)) == seed_key:
                matches.append(el.Id)
        return matches

    def do_select(self, sender, e):
        self.set_status("Searching...")
        with self.report_errors("Select Similar"):
            match_ids = self._matches()
            if not match_ids:
                if not self.status_text.Text or self.status_text.Text == "Searching...":
                    self.set_status("No matching elements found.")
                return
            ids = List[ElementId]()
            for eid in match_ids:
                ids.Add(eid)
            uidoc.Selection.SetElementIds(ids)
            self.Close()


def main():
    from pyrevit import forms
    elements = list(revit.get_selection().elements)
    if not elements:
        forms.alert("Select a single element first, then run Select Similar.",
                    title="Select Similar")
        return
    if len(elements) > 1:
        forms.alert("Select just one element to use as the seed.",
                    title="Select Similar")
        return
    SelectSimilarWindow(elements[0]).ShowDialog()


if __name__ == "__main__":
    main()
