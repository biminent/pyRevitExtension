# -*- coding: utf-8 -*-
__title__ = "Reload\nLink"
__doc__ = """Reload the selected DWG/CAD link(s) from their source files.

Select one or more linked DWGs in the model or a view, then run - each link is
reloaded from disk, picking up any changes made in AutoCAD. Imported (non-linked)
DWGs cannot be reloaded and are reported and skipped.

Part of Biminent Tools - biminent.com"""
__author__ = "Biminent"
__helpurl__ = "https://biminent.com"

from pyrevit import DB, forms, revit

from biminent import report

doc = revit.doc


def _cad_link_types(elements):
    """Unique reloadable CADLinkType objects behind the selected instances,
    keyed so each link is reloaded once even with several instances selected."""
    types = {}
    for el in elements:
        cad_type = el
        if isinstance(el, DB.ImportInstance):
            cad_type = doc.GetElement(el.GetTypeId())
        if isinstance(cad_type, DB.CADLinkType):
            types[cad_type.Id.IntegerValue] = cad_type
    return list(types.values())


def main():
    elements = list(revit.get_selection().elements)
    cad_types = _cad_link_types(elements)
    if not cad_types:
        forms.alert("Select one or more linked DWG/CAD elements first.",
                    title="Reload Link")
        return

    reloaded = 0
    embedded = 0
    failed = 0
    transaction = DB.Transaction(doc, u"Biminent \u00b7 Reload DWG Link")
    transaction.Start()
    try:
        for cad_type in cad_types:
            try:
                if not cad_type.IsExternalFileReference():
                    embedded += 1
                    continue
                cad_type.Reload()
                reloaded += 1
            except Exception:
                report.log_traceback("Reload Link")
                failed += 1
        transaction.Commit()
    except Exception:
        if transaction.HasStarted() and not transaction.HasEnded():
            transaction.RollBack()
        raise

    if reloaded and not embedded and not failed:
        try:
            forms.toast("Reloaded {} DWG link(s).".format(reloaded),
                        title="Biminent", appid="Biminent Tools")
        except Exception:
            forms.alert("Reloaded {} DWG link(s).".format(reloaded),
                        title="Reload Link")
        return

    notes = []
    if reloaded:
        notes.append("Reloaded {} link(s).".format(reloaded))
    if embedded:
        notes.append("{} selected item(s) are imported (not linked) and cannot "
                     "be reloaded.".format(embedded))
    if failed:
        notes.append("{} link(s) failed to reload - see the report.".format(failed))
    forms.alert("\n\n".join(notes) or "Nothing to reload.", title="Reload Link")


main()
