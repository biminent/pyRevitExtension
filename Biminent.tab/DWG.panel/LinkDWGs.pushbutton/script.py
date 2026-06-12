# -*- coding: utf-8 -*-
__title__ = "Link\nDWGs"
__doc__ = """Link multiple DWG files into the active Revit project."""
__author__ = "Biminent"
__helpurl__ = "https://biminent.com"

import os

import clr
from pyrevit import DB, forms, revit, script
from System.Windows.Controls import CheckBox

from biminent.ui import BiminentWindow


def get_dwg_files(folder):
    return sorted(
        os.path.join(folder, name)
        for name in os.listdir(folder)
        if name.lower().endswith(".dwg")
    )


def get_drafting_view_type(doc):
    view_types = DB.FilteredElementCollector(doc).OfClass(DB.ViewFamilyType)
    for view_type in view_types:
        if view_type.ViewFamily == DB.ViewFamily.Drafting:
            return view_type
    return None


def unique_view_name(doc, base_name):
    existing_names = set(
        view.Name
        for view in DB.FilteredElementCollector(doc).OfClass(DB.View)
    )
    if base_name not in existing_names:
        return base_name
    index = 2
    while True:
        candidate = "{} ({})".format(base_name, index)
        if candidate not in existing_names:
            return candidate
        index += 1


def make_import_options():
    options = DB.DWGImportOptions()
    options.AutoCorrectAlmostVHLines = True
    options.ColorMode = DB.ImportColorMode.Preserved
    options.OrientToView = True
    options.Placement = DB.ImportPlacement.Centered
    options.ThisViewOnly = True
    options.Unit = DB.ImportUnit.Default
    options.VisibleLayersOnly = True
    return options


class LinkDWGsWindow(BiminentWindow):
    def __init__(self):
        xaml = os.path.join(os.path.dirname(__file__), "LinkDWGsWindow.xaml")
        BiminentWindow.__init__(self, xaml)
        self.doc = revit.doc
        self.dwg_files = []
        self._set_status("Select a folder containing DWG files.")
        self._refresh_preview()

    def browse_folder(self, sender, e):
        folder = forms.pick_folder(title="Select folder containing DWG files")
        if not folder:
            return
        self.tb_folder.Text = folder
        self.dwg_files = get_dwg_files(folder)
        self._refresh_preview()

    def check_all(self, sender, e):
        for item in self.list_dwgs.Items:
            item.IsChecked = True
        self._update_count()

    def uncheck_all(self, sender, e):
        for item in self.list_dwgs.Items:
            item.IsChecked = False
        self._update_count()

    def item_checked(self, sender, e):
        self._update_count()

    def link_dwgs(self, sender, e):
        selected_files = self._selected_files()
        if not selected_files:
            self._set_status("No DWGs checked. Check at least one file to link.")
            return

        active_view = self.doc.ActiveView
        drafting_view_type = None
        if self.rb_drafting.IsChecked:
            drafting_view_type = get_drafting_view_type(self.doc)
            if drafting_view_type is None:
                self._set_status("No drafting view type was found in this project.")
                return

        linked = []
        failed = []
        transaction = DB.Transaction(self.doc, u"Biminent \u00b7 Link DWGs")
        transaction.Start()
        try:
            for dwg_file in selected_files:
                subtransaction = DB.SubTransaction(self.doc)
                subtransaction.Start()
                try:
                    target_view = active_view
                    if drafting_view_type is not None:
                        target_view = DB.ViewDrafting.Create(self.doc, drafting_view_type.Id)
                        view_name = os.path.splitext(os.path.basename(dwg_file))[0]
                        target_view.Name = unique_view_name(self.doc, view_name)

                    linked_element_id = clr.Reference[DB.ElementId]()
                    self.doc.Link(dwg_file, make_import_options(), target_view, linked_element_id)
                    subtransaction.Commit()
                    linked.append((dwg_file, target_view.Name))
                except Exception as link_error:
                    try:
                        subtransaction.RollBack()
                    except Exception:
                        pass
                    failed.append((dwg_file, str(link_error)))

            if linked:
                transaction.Commit()
            else:
                transaction.RollBack()
        except Exception:
            try:
                transaction.RollBack()
            except Exception:
                pass
            raise

        self._report_results(linked, failed)

    def _refresh_preview(self):
        self.list_dwgs.Items.Clear()
        for dwg_file in self.dwg_files:
            item = CheckBox()
            item.Content = os.path.basename(dwg_file)
            item.Tag = dwg_file
            item.ToolTip = dwg_file
            item.IsChecked = True
            item.Checked += self.item_checked
            item.Unchecked += self.item_checked
            self.list_dwgs.Items.Add(item)

        if not self.tb_folder.Text:
            self.lbl_count.Text = "0/0"
            self.btn_link.IsEnabled = False
            self._set_status("Select a folder containing DWG files.")
        elif not self.dwg_files:
            self.lbl_count.Text = "0/0"
            self.btn_link.IsEnabled = False
            self._set_status("0 DWGs found in selected folder.")
        else:
            self._update_count()

    def _selected_files(self):
        return [
            str(item.Tag)
            for item in self.list_dwgs.Items
            if item.IsChecked
        ]

    def _update_count(self):
        checked = len(self._selected_files())
        total = len(self.dwg_files)
        self.lbl_count.Text = "{}/{}".format(checked, total)
        self.btn_link.IsEnabled = checked > 0
        if total:
            self._set_status("{} checked - {} total DWG files.".format(checked, total))

    def _set_status(self, message):
        self.status_text.Text = message

    def _report_results(self, linked, failed):
        output = script.get_output()
        if linked:
            output.print_md("### Linked DWGs")
            for dwg_file, view_name in linked:
                output.print_md("- `{}` -> `{}`".format(os.path.basename(dwg_file), view_name))

        if failed:
            output.print_md("### Failed DWGs")
            for dwg_file, error in failed:
                output.print_md("- `{}`: {}".format(os.path.basename(dwg_file), error))

        if failed:
            self._set_status(
                "Linked {} - {} failed. See pyRevit output.".format(len(linked), len(failed))
            )
        else:
            self._set_status("Linked {} DWG file(s).".format(len(linked)))


if __name__ == "__main__":
    LinkDWGsWindow().ShowDialog()
