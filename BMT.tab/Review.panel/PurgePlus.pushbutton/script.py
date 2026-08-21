# -*- coding: utf-8 -*-
import os

from pyrevit import revit
from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    ElementId,
    FilteredElementCollector,
    ImportInstance,
    Transaction,
    View,
    ViewSheet,
    ViewType,
    Viewport,
)

from biminent.ui import BiminentWindow
from biminent.compat import element_id_value
from biminent import report

doc = revit.doc


# ---- candidate collectors --------------------------------------------------
# Each returns a list of ElementId to delete. They must be cheap enough to run
# on load (we show the counts before the user commits).

_DELETABLE_VIEW_TYPES = set([
    ViewType.FloorPlan, ViewType.CeilingPlan, ViewType.AreaPlan,
    ViewType.EngineeringPlan, ViewType.Section, ViewType.Elevation,
    ViewType.Detail, ViewType.ThreeD, ViewType.DraftingView,
    ViewType.Rendering,
])


def _unplaced_rooms():
    out = []
    for r in (FilteredElementCollector(doc)
              .OfCategory(BuiltInCategory.OST_Rooms)
              .WhereElementIsNotElementType()):
        if r.Location is None:
            out.append(r.Id)
    return out


def _unplaced_areas():
    out = []
    for a in (FilteredElementCollector(doc)
              .OfCategory(BuiltInCategory.OST_Areas)
              .WhereElementIsNotElementType()):
        if a.Location is None:
            out.append(a.Id)
    return out


def _unenclosed_areas():
    out = []
    for a in (FilteredElementCollector(doc)
              .OfCategory(BuiltInCategory.OST_Areas)
              .WhereElementIsNotElementType()):
        try:
            if a.Location is not None and a.Area == 0:
                out.append(a.Id)
        except Exception:
            continue
    return out


def _views_not_on_sheets():
    placed = set()
    for vp in FilteredElementCollector(doc).OfClass(Viewport):
        placed.add(element_id_value(vp.ViewId))
    active_id = element_id_value(doc.ActiveView.Id)
    out = []
    for v in FilteredElementCollector(doc).OfClass(View):
        try:
            if v.IsTemplate:
                continue
            if v.ViewType not in _DELETABLE_VIEW_TYPES:
                continue
            if element_id_value(v.Id) == active_id:
                continue
            if element_id_value(v.Id) in placed:
                continue
            out.append(v.Id)
        except Exception:
            continue
    return out


def _empty_sheets():
    out = []
    for sheet in FilteredElementCollector(doc).OfClass(ViewSheet):
        try:
            if sheet.IsPlaceholder:
                continue
            if sheet.GetAllViewports().Count == 0:
                out.append(sheet.Id)
        except Exception:
            continue
    return out


def _scope_box_used_ids():
    """Ids of scope boxes referenced by any view crop or datum element."""
    used = set()
    for v in FilteredElementCollector(doc).OfClass(View):
        try:
            p = v.get_Parameter(BuiltInParameter.VIEWER_VOLUME_OF_INTEREST_CROP)
            if p is not None and p.AsElementId() != ElementId.InvalidElementId:
                used.add(element_id_value(p.AsElementId()))
        except Exception:
            continue
    for bic in (BuiltInCategory.OST_Grids, BuiltInCategory.OST_Levels,
                BuiltInCategory.OST_CLines):
        for d in (FilteredElementCollector(doc)
                  .OfCategory(bic)
                  .WhereElementIsNotElementType()):
            try:
                p = d.get_Parameter(BuiltInParameter.DATUM_VOLUME_OF_INTEREST)
                if p is not None and p.AsElementId() != ElementId.InvalidElementId:
                    used.add(element_id_value(p.AsElementId()))
            except Exception:
                continue
    return used


def _unused_scope_boxes():
    used = _scope_box_used_ids()
    out = []
    for sb in (FilteredElementCollector(doc)
               .OfCategory(BuiltInCategory.OST_VolumeOfInterest)
               .WhereElementIsNotElementType()):
        if element_id_value(sb.Id) not in used:
            out.append(sb.Id)
    return out


def _imported_dwgs():
    out = []
    for imp in FilteredElementCollector(doc).OfClass(ImportInstance):
        try:
            if not imp.IsLinked:
                out.append(imp.Id)
        except Exception:
            continue
    return out


# ---- operations ------------------------------------------------------------

class PurgeOp(object):
    def __init__(self, title, tooltip, collector):
        self.title = title
        self.tooltip = tooltip
        self._collector = collector
        self.ids = []
        self.checked = False

    def recount(self):
        try:
            self.ids = list(self._collector())
        except Exception:
            report.log_traceback("Purge+ - " + self.title)
            self.ids = []

    @property
    def has_items(self):
        return len(self.ids) > 0

    @property
    def Label(self):
        return u"{}  \u2014  {}".format(self.title, len(self.ids))


def _build_ops():
    return [
        PurgeOp("Unplaced rooms",
                "Rooms that were never placed in a plan", _unplaced_rooms),
        PurgeOp("Unplaced areas",
                "Areas that were never placed in a plan", _unplaced_areas),
        PurgeOp("Unenclosed areas",
                "Placed areas with no boundary (area = 0)", _unenclosed_areas),
        PurgeOp("Views not on sheets",
                "Plans, sections, 3D and drafting views not placed on any sheet "
                "(the active view is never included)", _views_not_on_sheets),
        PurgeOp("Sheets with no views",
                "Sheets that have no viewports placed on them", _empty_sheets),
        PurgeOp("Unused scope boxes",
                "Scope boxes not referenced by any view crop or datum",
                _unused_scope_boxes),
        PurgeOp("Imported DWGs",
                "Imported (non-linked) DWGs - links are never touched",
                _imported_dwgs),
    ]


class PurgePlusWindow(BiminentWindow):
    def __init__(self):
        xaml = os.path.join(os.path.dirname(__file__), "PurgePlusWindow.xaml")
        self._ops = _build_ops()
        for op in self._ops:
            op.recount()
        BiminentWindow.__init__(self, xaml)
        self._refresh()

    def _refresh(self):
        self.list_ops.ItemsSource = None
        self.list_ops.ItemsSource = self._ops
        self._refresh_counts()

    def _refresh_counts(self):
        total = sum(len(op.ids) for op in self._ops if op.checked)
        self.lbl_total.Text = "{} to delete".format(total)
        self.btn_purge.IsEnabled = total > 0

    def item_checked(self, sender, e):
        item = sender.DataContext
        if item is not None:
            item.checked = True
            self._refresh_counts()

    def item_unchecked(self, sender, e):
        item = sender.DataContext
        if item is not None:
            item.checked = False
            self._refresh_counts()

    def check_all(self, sender, e):
        for op in self._ops:
            if op.has_items:
                op.checked = True
        self._refresh()

    def check_none(self, sender, e):
        for op in self._ops:
            op.checked = False
        self._refresh()

    def do_purge(self, sender, e):
        ids = []
        for op in self._ops:
            if op.checked:
                ids.extend(op.ids)
        if not ids:
            return

        self.set_status("Purging...")
        with self.report_errors("Purge+"):
            deleted = 0
            t = Transaction(doc, u"Biminent \u00b7 Purge+")
            t.Start()
            try:
                for eid in ids:
                    try:
                        # An id may already be gone (e.g. a view deleted with its
                        # sheet); skip those instead of aborting the whole purge.
                        if doc.GetElement(eid) is None:
                            continue
                        removed = doc.Delete(eid)
                        deleted += removed.Count if removed is not None else 1
                    except Exception:
                        continue
                t.Commit()
            except Exception:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                raise

            # Recompute so the user sees the cleaned-up state and can purge more.
            for op in self._ops:
                op.recount()
                op.checked = False
            self._refresh()
            self.set_status("Purged {} element(s).".format(deleted))


if __name__ == "__main__":
    PurgePlusWindow().ShowDialog()
