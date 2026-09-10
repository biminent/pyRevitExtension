# -*- coding: utf-8 -*-
"""Copy selected element IDs to the clipboard without opening a window."""

from pyrevit import revit, script


def main():
    uidoc = revit.uidoc
    if uidoc is None:
        return

    element_ids = uidoc.Selection.GetElementIds()
    if not element_ids:
        return

    # ToString supports both older 32-bit and newer 64-bit ElementIds.
    id_strings = [element_id.ToString() for element_id in element_ids]
    script.clipboard_copy(", ".join(sorted(id_strings, key=int)))


if __name__ == "__main__":
    main()
