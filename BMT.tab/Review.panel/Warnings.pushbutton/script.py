# -*- coding: utf-8 -*-
__title__   = "Review\nWarnings"
__doc__     = """Review the model's warnings, grouped by type.

Each row is one kind of warning with how many times it occurs. Check the
types you want to deal with, then:

  - Select - make every element involved the current Revit selection, or
  - Isolate in view - temporarily isolate those elements in the active view
    so you can see them in context (use Revit's "Reset Temporary Hide/Isolate"
    to restore the view).

Part of Biminent Tools - biminent.com"""
__author__  = "Biminent"
__helpurl__ = "https://biminent.com"

import os

from pyrevit import revit
from Autodesk.Revit.DB import (
    ElementId,
    Transaction,
)
from System.Collections.Generic import List

from biminent.ui import BiminentWindow

doc = revit.doc
uidoc = revit.uidoc


class WarningGroup(object):
    """One kind of warning: its text, the elements involved, and a count."""
    def __init__(self, description, element_ids):
        self.description = description
        self.element_ids = element_ids  # set of ElementId
        self.checked = False

    @property
    def Label(self):
        return u"({}) {}".format(len(self.element_ids), self.description)


def _collect_warnings():
    """Group the document's warnings by description text, unioning the failing
    elements of each occurrence."""
    groups = {}
    for failure in doc.GetWarnings():
        try:
            text = failure.GetDescriptionText()
        except Exception:
            text = "(unnamed warning)"
        bucket = groups.get(text)
        if bucket is None:
            bucket = set()
            groups[text] = bucket
        try:
            for eid in failure.GetFailingElements():
                bucket.add(eid)
        except Exception:
            pass
    items = [WarningGroup(text, ids) for text, ids in groups.items()]
    return sorted(items, key=lambda g: g.description.lower())


class WarningsWindow(BiminentWindow):
    def __init__(self):
        xaml = os.path.join(os.path.dirname(__file__), "WarningsWindow.xaml")
        self._groups = _collect_warnings()
        BiminentWindow.__init__(self, xaml)
        self._refresh()
        if not self._groups:
            self.set_status("No warnings in this model.")

    @staticmethod
    def _visible(items, text):
        text = (text or "").lower()
        if not text:
            return list(items)
        return [i for i in items if text in i.description.lower()]

    def _refresh(self):
        visible = self._visible(self._groups, self.tb_filter.Text)
        self.list_warnings.ItemsSource = None
        self.list_warnings.ItemsSource = visible
        self._refresh_counts()

    def _refresh_counts(self):
        checked = sum(1 for g in self._groups if g.checked)
        self.lbl_count.Text = "{}/{}".format(checked, len(self._groups))
        enabled = checked > 0
        self.btn_select.IsEnabled = enabled
        self.btn_isolate.IsEnabled = enabled

    def filter_changed(self, sender, e):
        self._refresh()

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
        for g in self._visible(self._groups, self.tb_filter.Text):
            g.checked = True
        self._refresh()

    def check_none(self, sender, e):
        for g in self._visible(self._groups, self.tb_filter.Text):
            g.checked = False
        self._refresh()

    def _checked_ids(self):
        ids = set()
        for g in self._groups:
            if g.checked:
                ids.update(g.element_ids)
        return ids

    def do_select(self, sender, e):
        with self.report_errors("Review Warnings"):
            wanted = self._checked_ids()
            if not wanted:
                return
            ids = List[ElementId]()
            for eid in wanted:
                ids.Add(eid)
            uidoc.Selection.SetElementIds(ids)
            self.Close()

    def do_isolate(self, sender, e):
        with self.report_errors("Review Warnings"):
            wanted = self._checked_ids()
            if not wanted:
                return
            view = doc.ActiveView
            ids = List[ElementId]()
            for eid in wanted:
                ids.Add(eid)
            t = Transaction(doc, u"Biminent \u00b7 Isolate warning elements")
            t.Start()
            try:
                view.IsolateElementsTemporary(ids)
                t.Commit()
            except Exception:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                raise
            uidoc.Selection.SetElementIds(ids)
            self.Close()


if __name__ == "__main__":
    WarningsWindow().ShowDialog()
