# -*- coding: utf-8 -*-
"""Revit API differences smoothed over, so tools run on every supported version.

ElementId changed shape across releases:
  * Revit 2022-2023 - only `IntegerValue` (Int32); only the ElementId(Int32) ctor.
  * Revit 2024-2025 - both `IntegerValue` and the new `Value` (Int64); both ctors.
  * Revit 2026+     - `IntegerValue` and the ElementId(Int32) ctor are gone.

No single spelling works everywhere, so the shape is resolved once at import - a Revit
session never changes version, so this is safe under pyRevit rocket mode - instead of
per call, because the callers loop over every element in the model.

Presence/absence differences like the above are handled by probing the API itself, so
the check can't fall out of step with what Revit actually exposes. REVIT_VERSION is for
the other kind: an API that keeps its name but changes behaviour, where only the release
number tells you which way to go.
"""
from System import Convert
from Autodesk.Revit.DB import ElementId

try:
    from pyrevit import HOST_APP
    REVIT_VERSION = int(HOST_APP.version)   # Application.VersionNumber, e.g. "2026"
except Exception:
    REVIT_VERSION = None                    # not running inside a Revit host

_HAS_VALUE = hasattr(ElementId.InvalidElementId, "Value")

if _HAS_VALUE:
    def element_id_value(element_id):
        """The numeric value of an ElementId (Revit 2024+: Int64)."""
        return element_id.Value

    def to_element_id(value):
        """An ElementId from a numeric value (Revit 2024+: Int64 ctor)."""
        return ElementId(Convert.ToInt64(value))
else:
    def element_id_value(element_id):
        """The numeric value of an ElementId (Revit 2022-2023: Int32)."""
        return element_id.IntegerValue

    def to_element_id(value):
        """An ElementId from a numeric value (Revit 2022-2023: Int32 ctor)."""
        return ElementId(Convert.ToInt32(value))
