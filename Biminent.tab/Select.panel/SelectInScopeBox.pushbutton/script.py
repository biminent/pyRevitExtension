# -*- coding: utf-8 -*-
__title__   = "Select in\nScope Box"
__doc__     = """Select every element inside one or more scope boxes, by category.

Check the scope boxes and the categories you care about, then Select -
the matching elements become the Revit selection and the window closes so
you can act on them. Works with rotated scope boxes.

Part of Biminent Tools - biminent.com"""
__author__  = "Biminent"
__helpurl__ = "https://biminent.com"

import os

from pyrevit import revit
from Autodesk.Revit.DB import (
    BoundingBoxXYZ,
    BuiltInCategory,
    BuiltInParameter,
    CategoryType,
    Curve,
    CurveLoop,
    ElementId,
    ElementIntersectsSolidFilter,
    FilteredElementCollector,
    GeometryCreationUtilities,
    Line,
    Options,
    SolidCurveIntersectionOptions,
    SolidUtils,
    Transform,
    XYZ,
)
from System.Collections.Generic import List

from biminent import report
from biminent.ui import BiminentWindow

doc = revit.doc
uidoc = revit.uidoc


# ---- scope-box geometry ----------------------------------------------------
# Builds an oriented solid from a scope box, so the test works even when the
# scope box is rotated in plan. (Geometry approach ported from the author's
# own har.extension SelectInScopeBox tool.)

def _is_vertical_line(line):
    return line.Direction.CrossProduct(XYZ.BasisZ).IsAlmostEqualTo(XYZ.Zero)


def _is_up_vector(xyz):
    return xyz.Normalize().IsAlmostEqualTo(XYZ.BasisZ)


def _lower_z_end(line):
    return line.GetEndPoint(0 if line.Direction.Z > 0 else 1)


def _opposite_end(line, end_point):
    a = line.GetEndPoint(0)
    b = line.GetEndPoint(1)
    if b.IsAlmostEqualTo(end_point):
        return a
    if a.IsAlmostEqualTo(end_point):
        return b
    return None


def _scope_box_bbox(scope_box):
    geom = scope_box.get_Geometry(Options())
    lines = [l for l in geom if isinstance(l, Line)] if geom is not None else []
    if not lines:
        raise ValueError("scope box returned no edge lines")
    vertical = [l for l in lines if _is_vertical_line(l)]
    if not vertical:
        raise ValueError("scope box has no vertical edges")
    origin = _lower_z_end(vertical[0])

    vectors = [p - origin
               for p in (_opposite_end(l, origin) for l in lines)
               if p is not None]
    v_z = [v for v in vectors if _is_up_vector(v)][0]
    v1, v2 = [v for v in vectors if not v.IsAlmostEqualTo(v_z)]
    # Keep a right-handed system so the transform is valid.
    if v1.CrossProduct(v2).Normalize().IsAlmostEqualTo(v_z.Normalize()):
        v_x, v_y = v1, v2
    else:
        v_x, v_y = v2, v1

    t = Transform.Identity
    t.Origin = origin
    t.BasisX = v_x.Normalize()
    t.BasisY = v_y.Normalize()
    t.BasisZ = v_z.Normalize()
    bbox = BoundingBoxXYZ()
    bbox.Transform = t
    bbox.Min = XYZ.Zero
    bbox.Max = XYZ(v_x.GetLength(), v_y.GetLength(), v_z.GetLength())
    return bbox


def _solid_from_bbox(bbox):
    pts = [
        XYZ(bbox.Min.X, bbox.Min.Y, bbox.Min.Z),
        XYZ(bbox.Max.X, bbox.Min.Y, bbox.Min.Z),
        XYZ(bbox.Max.X, bbox.Max.Y, bbox.Min.Z),
        XYZ(bbox.Min.X, bbox.Max.Y, bbox.Min.Z),
    ]
    edges = List[Curve]()
    for i in range(4):
        edges.Add(Line.CreateBound(pts[i], pts[(i + 1) % 4]))
    loops = List[CurveLoop]()
    loops.Add(CurveLoop.Create(edges))
    height = bbox.Max.Z - bbox.Min.Z
    if height <= 1e-6 or bbox.Max.X <= 1e-6 or bbox.Max.Y <= 1e-6:
        return None  # degenerate scope box - skip rather than risk a bad solid
    solid = GeometryCreationUtilities.CreateExtrusionGeometry(loops, XYZ.BasisZ, height)
    solid = SolidUtils.CreateTransformed(solid, bbox.Transform)
    if solid is None or solid.Volume <= 1e-9:
        return None
    return solid


def _element_level_id(el):
    """Best-effort level ElementId for an element, or None if it has none.

    Tries the direct `LevelId` property first, then the common level-bearing
    parameters (groups carry GROUP_LEVEL, hosted families a level param), so
    the optional level filter works across the categories users actually pick."""
    try:
        lid = el.LevelId
        if lid is not None and lid != ElementId.InvalidElementId:
            return lid
    except Exception:
        pass
    for bip in (BuiltInParameter.GROUP_LEVEL,
                BuiltInParameter.FAMILY_LEVEL_PARAM,
                BuiltInParameter.SCHEDULE_LEVEL_PARAM,
                BuiltInParameter.INSTANCE_REFERENCE_LEVEL_PARAM,
                BuiltInParameter.INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM,
                BuiltInParameter.ROOM_LEVEL_ID,
                BuiltInParameter.LEVEL_PARAM):
        try:
            p = el.get_Parameter(bip)
            if p is not None and p.HasValue:
                lid = p.AsElementId()
                if lid is not None and lid != ElementId.InvalidElementId:
                    return lid
        except Exception:
            continue
    return None


def _elements_in_solid(solid, category_id, level_id=None):
    """Element ids of one category inside the solid. Uses the fast solid filter,
    then falls back to a location-point test for categories the filter misses
    (Rooms, Areas - they have no solid geometry to intersect).

    When `level_id` is given, only elements on that level are returned (elements
    without a resolvable level are dropped)."""
    def _passes_level(element):
        if level_id is None:
            return True
        return _element_level_id(element) == level_id

    found = [
        el.Id
        for el in (FilteredElementCollector(doc)
                   .OfCategoryId(category_id)
                   .WhereElementIsNotElementType()
                   .WherePasses(ElementIntersectsSolidFilter(solid))
                   .ToElements())
        if _passes_level(el)
    ]
    if found:
        return found

    opts = SolidCurveIntersectionOptions()
    fallback = []
    for el in (FilteredElementCollector(doc)
               .OfCategoryId(category_id)
               .WhereElementIsNotElementType()
               .ToElements()):
        if not _passes_level(el):
            continue
        point = _element_point(el)
        if point is None:
            continue
        probe = Line.CreateBound(point, XYZ(point.X, point.Y, point.Z + 1.0))
        try:
            if solid.IntersectWithCurve(probe, opts).SegmentCount > 0:
                fallback.append(el.Id)
        except Exception:
            continue
    return fallback


def _element_point(el):
    try:
        location = el.Location
        if location is not None and hasattr(location, "Point"):
            return location.Point
    except Exception:
        pass
    try:
        box = el.get_BoundingBox(None)
        return Line.CreateBound(box.Min, box.Max).Evaluate(0.5, True)
    except Exception:
        return None


# ---- list items ------------------------------------------------------------

class CheckItem(object):
    def __init__(self, label, payload):
        self.Label = label
        self.payload = payload
        self.checked = False


def _collect_scope_boxes():
    boxes = (FilteredElementCollector(doc)
             .OfCategory(BuiltInCategory.OST_VolumeOfInterest)
             .WhereElementIsNotElementType()
             .ToElements())
    return [CheckItem(b.Name, b) for b in sorted(boxes, key=lambda b: b.Name.lower())]


def _collect_categories():
    items = []
    for cat in doc.Settings.Categories:
        try:
            if cat.CategoryType != CategoryType.Model or not cat.IsVisibleInUI:
                continue
        except Exception:
            continue
        items.append(CheckItem(cat.Name, cat.Id))
    return sorted(items, key=lambda i: i.Label.lower())


def _collect_levels():
    """Level dropdown items: "All levels" first, then levels low-to-high.

    payload is None for the "all" entry (no level filter) or the level's
    ElementId otherwise."""
    levels = (FilteredElementCollector(doc)
              .OfCategory(BuiltInCategory.OST_Levels)
              .WhereElementIsNotElementType()
              .ToElements())
    items = [CheckItem("All levels", None)]
    for lvl in sorted(levels, key=lambda l: l.Elevation):
        items.append(CheckItem(lvl.Name, lvl.Id))
    return items


# ---- window ----------------------------------------------------------------

class SelectInScopeBoxWindow(BiminentWindow):
    def __init__(self):
        xaml = os.path.join(os.path.dirname(__file__), "SelectInScopeBoxWindow.xaml")
        self._scopes = _collect_scope_boxes()
        self._cats = _collect_categories()
        self._levels = _collect_levels()
        BiminentWindow.__init__(self, xaml)
        self.cb_level.ItemsSource = self._levels
        self.cb_level.SelectedIndex = 0
        self._refresh_scopes()
        self._refresh_cats()
        if not self._scopes:
            self.status_text.Text = "No scope boxes in this model."

    # -- level filter --

    def _selected_level_id(self):
        item = self.cb_level.SelectedItem
        return item.payload if item is not None else None

    # -- shared checklist helpers --

    @staticmethod
    def _visible(items, text):
        text = (text or "").lower()
        if not text:
            return list(items)
        return [i for i in items if text in i.Label.lower()]

    def _refresh_scopes(self):
        visible = self._visible(self._scopes, self.tb_scope_filter.Text)
        self.list_scopes.ItemsSource = None
        self.list_scopes.ItemsSource = visible
        self._refresh_counts()

    def _refresh_cats(self):
        visible = self._visible(self._cats, self.tb_cat_filter.Text)
        self.list_cats.ItemsSource = None
        self.list_cats.ItemsSource = visible
        self._refresh_counts()

    def _refresh_counts(self):
        s_checked = sum(1 for i in self._scopes if i.checked)
        c_checked = sum(1 for i in self._cats if i.checked)
        self.lbl_scope_count.Text = "{}/{}".format(s_checked, len(self._scopes))
        self.lbl_cat_count.Text = "{}/{}".format(c_checked, len(self._cats))
        self.btn_select.IsEnabled = s_checked > 0 and c_checked > 0

    # -- events: scope boxes --

    def scope_filter_changed(self, sender, e):
        self._refresh_scopes()

    def scope_checked(self, sender, e):
        item = sender.DataContext
        if item is None:
            return
        item.checked = True
        self._refresh_counts()

    def scope_unchecked(self, sender, e):
        item = sender.DataContext
        if item is None:
            return
        item.checked = False
        self._refresh_counts()

    def scopes_check_all(self, sender, e):
        for i in self._visible(self._scopes, self.tb_scope_filter.Text):
            i.checked = True
        self._refresh_scopes()

    def scopes_check_none(self, sender, e):
        for i in self._visible(self._scopes, self.tb_scope_filter.Text):
            i.checked = False
        self._refresh_scopes()

    # -- events: categories --

    def cat_filter_changed(self, sender, e):
        self._refresh_cats()

    def cat_checked(self, sender, e):
        item = sender.DataContext
        if item is None:
            return
        item.checked = True
        self._refresh_counts()

    def cat_unchecked(self, sender, e):
        item = sender.DataContext
        if item is None:
            return
        item.checked = False
        self._refresh_counts()

    def cats_check_all(self, sender, e):
        for i in self._visible(self._cats, self.tb_cat_filter.Text):
            i.checked = True
        self._refresh_cats()

    def cats_check_none(self, sender, e):
        for i in self._visible(self._cats, self.tb_cat_filter.Text):
            i.checked = False
        self._refresh_cats()

    # -- select --

    def do_select(self, sender, e):
        scopes = [i.payload for i in self._scopes if i.checked]
        cat_ids = [i.payload for i in self._cats if i.checked]
        if not scopes or not cat_ids:
            return

        level_id = self._selected_level_id()
        self.set_status("Searching...")
        with self.report_errors("Select in Scope Box"):
            found = set()
            failed = 0
            for box in scopes:
                try:
                    solid = _solid_from_bbox(_scope_box_bbox(box))
                except Exception:
                    # one unreadable box shouldn't abort the rest - log and skip
                    report.log_traceback("Select in Scope Box - " + box.Name)
                    solid = None
                if solid is None:
                    failed += 1
                    continue
                for cat_id in cat_ids:
                    try:
                        for eid in _elements_in_solid(solid, cat_id, level_id):
                            found.add(eid)
                    except Exception:
                        continue  # skip a category Revit can't intersect-test

            if not found:
                if failed:
                    self.set_status(
                        "{} scope box(es) could not be read - see the report.".format(failed))
                else:
                    suffix = "" if level_id is None else " on the selected level"
                    self.set_status(
                        "No elements found in the checked scope boxes{}.".format(suffix))
                return

            ids = List[ElementId]()
            for eid in found:
                ids.Add(eid)
            uidoc.Selection.SetElementIds(ids)
            self.Close()  # close so the highlighted elements are usable in Revit


if __name__ == "__main__":
    # Modal: keeps every Revit API call inside the command's API context.
    # A modeless .Show() here would call the API out of context and crash Revit.
    SelectInScopeBoxWindow().ShowDialog()
