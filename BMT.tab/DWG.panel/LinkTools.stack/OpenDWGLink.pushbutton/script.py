# -*- coding: utf-8 -*-
__title__ = "Open\nLink"
__doc__ = """Open the source file of the selected DWG/CAD link in its default
Windows program (e.g. AutoCAD).

Select one or more linked DWGs in the model or a view, then run - each link's
external file is opened with whatever application Windows associates with it.
Imported (non-linked) DWGs and links whose source file is missing are reported
and skipped.

Part of Biminent Tools - biminent.com"""
__author__ = "Biminent"
__helpurl__ = "https://biminent.com"

import os

from pyrevit import DB, forms, revit, script

from biminent import report

doc = revit.doc


def _cad_link_types(elements):
    """Unique CADLinkType objects behind the selected import/link instances,
    keyed so each source file is handled once even with several instances."""
    types = {}
    for el in elements:
        cad_type = el
        if isinstance(el, DB.ImportInstance):
            cad_type = doc.GetElement(el.GetTypeId())
        if isinstance(cad_type, DB.CADLinkType):
            types[cad_type.Id.IntegerValue] = cad_type
    return list(types.values())


def _external_path(cad_type):
    """User-visible absolute path of a linked CAD type, or None if it is an
    embedded import (not an external link)."""
    try:
        if not cad_type.IsExternalFileReference():
            return None
        ext_ref = cad_type.GetExternalFileReference()
        path = DB.ModelPathUtils.ConvertModelPathToUserVisiblePath(
            ext_ref.GetAbsolutePath())
        return path or None
    except Exception:
        return None


def main():
    elements = list(revit.get_selection().elements)
    cad_types = _cad_link_types(elements)
    if not cad_types:
        forms.alert("Select one or more linked DWG/CAD elements first.",
                    title="Open Link")
        return

    opened = 0
    embedded = 0
    missing = []
    for cad_type in cad_types:
        path = _external_path(cad_type)
        if path is None:
            embedded += 1
            continue
        if not os.path.isfile(path):
            missing.append(path)
            continue
        try:
            os.startfile(path, "open")
            opened += 1
        except Exception:
            report.log_traceback("Open Link")
            missing.append(path)

    if opened and not missing and not embedded:
        return  # clean success - the file(s) just opened, no need to interrupt

    notes = []
    if opened:
        notes.append("Opened {} file(s).".format(opened))
    if embedded:
        notes.append("{} selected item(s) are imported (not linked) and have "
                     "no source file.".format(embedded))
    if missing:
        notes.append("Could not open:\n  " + "\n  ".join(missing))
    forms.alert("\n\n".join(notes) or "Nothing to open.", title="Open Link")


main()
