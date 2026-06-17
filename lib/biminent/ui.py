# -*- coding: utf-8 -*-
"""Biminent branded WPF window base for pyRevit tools.

Usage in a pushbutton script:

    from biminent.ui import BiminentWindow

    class MyToolWindow(BiminentWindow):
        def __init__(self):
            BiminentWindow.__init__(self, 'MyTool.xaml')

    MyToolWindow().ShowDialog()

The Biminent theme (lib/resources/theme/*.xaml) is merged into the window
resources after the XAML is loaded, so tool XAML must reference theme
resources with {DynamicResource ...}, never {StaticResource ...}.
"""
import os
import clr

clr.AddReference("System")
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")

from pyrevit.framework import wpf  # noqa: E402  (engine-aware pyRevit WPF loader)
from System import IntPtr, Uri, UriKind  # noqa: E402
from System.Diagnostics import Process, ProcessStartInfo  # noqa: E402
from System.Windows import Window, ResourceDictionary  # noqa: E402
from System.Windows.Input import Cursors, MouseButtonState  # noqa: E402
from System.Windows.Interop import WindowInteropHelper  # noqa: E402
from System.Windows.Media.Imaging import BitmapCacheOption, BitmapImage  # noqa: E402

from biminent import URL_WEBSITE  # noqa: E402
from biminent import report  # noqa: E402

# Merge order matters: design tokens first, then component styles.
THEME_FILES = [
    "Colors.xaml",
    "Typography.xaml",
    "Buttons.xaml",
    "Inputs.xaml",
    "DataControls.xaml",
    "Containers.xaml",
    "ProgressIndicators.xaml",
    "ScrollBars.xaml",
    "WindowChrome.xaml",
    "Brand.xaml",
]

_RESOURCES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")
THEME_DIR = os.path.join(_RESOURCES_DIR, "theme")
LOGO_PATH = os.path.join(_RESOURCES_DIR, "brand", "Biminent_Logo_Small.png")


def load_theme(window):
    """Merge the Biminent theme dictionaries into a WPF window."""
    for name in THEME_FILES:
        path = os.path.join(THEME_DIR, name)
        rd = ResourceDictionary()
        rd.Source = Uri(path, UriKind.Absolute)
        window.Resources.MergedDictionaries.Add(rd)


def open_url(url):
    """Open a link in the default browser.

    Must go through the shell: on modern .NET (Revit 2025's runtime)
    Process.Start defaults to UseShellExecute=False, so passing a URL string
    makes it try to launch the URL as an executable - which fails with
    "system cannot find the file specified". ShellExecute hands the URL to the
    OS to resolve with the default browser.
    """
    psi = ProcessStartInfo(url)
    psi.UseShellExecute = True
    Process.Start(psi)


# Title-bar tinting via the Windows 11 DWM API (build 22000+).
# COLORREF is 0x00BBGGRR. Primary #1E3A5F -> R=1E G=3A B=5F -> 0x005F3A1E.
PRIMARY_COLORREF = 0x005F3A1E
WHITE_COLORREF = 0x00FFFFFF
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36


def tint_titlebar(handle, caption_colorref, text_colorref):
    """Color the native title bar (caption + text). No-op before Windows 11."""
    if not handle or handle == IntPtr.Zero:
        return
    import ctypes
    dwm = ctypes.windll.dwmapi
    dwm.DwmSetWindowAttribute.argtypes = [
        ctypes.c_void_p, ctypes.c_uint,
        ctypes.POINTER(ctypes.c_int), ctypes.c_uint]
    hwnd = handle.ToInt64()
    for attr, value in ((_DWMWA_CAPTION_COLOR, caption_colorref),
                        (_DWMWA_TEXT_COLOR, text_colorref)):
        v = ctypes.c_int(value)
        dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))


def set_revit_owner(window):
    """Parent a WPF window to the Revit main window.

    Without an owner, a modal dialog disappears behind Revit when the user
    alt-tabs away and back, while still blocking input — Revit looks frozen.
    """
    handle = None
    try:
        from pyrevit import HOST_APP
        handle = HOST_APP.uiapp.MainWindowHandle  # Revit 2019+
    except Exception:
        pass
    if not handle:
        try:
            clr.AddReference("AdWindows")
            from Autodesk.Windows import ComponentManager
            handle = ComponentManager.ApplicationWindow
        except Exception:
            pass
    if handle:
        try:
            WindowInteropHelper(window).Owner = handle
        except Exception:
            pass


class BiminentWindow(Window):
    """Base class for all Biminent tool windows.

    Loads the tool XAML (path relative to the calling script's folder is
    resolved by the caller) and merges the brand theme. Provides common
    handlers for borderless-window chrome: drag, close, and hyperlinks.
    """

    def __init__(self, xaml_path):
        wpf.LoadComponent(self, xaml_path)
        load_theme(self)
        set_revit_owner(self)
        self._setup_brand_logo()
        # Tint the native title bar once it has a window handle (Windows 11).
        self.SourceInitialized += self._tint_titlebar

    def _tint_titlebar(self, sender, e):
        try:
            handle = WindowInteropHelper(self).Handle
            tint_titlebar(handle, PRIMARY_COLORREF, WHITE_COLORREF)
        except Exception:
            pass  # pre-Win11 / unsupported: native grey bar, no harm

    def _setup_brand_logo(self):
        """Wire the brand block if the window XAML declares it.

        <Image x:Name="brand_logo"/> gets the Biminent logo; an optional
        <TextBlock x:Name="brand_wordmark"/> next to it is wired the same
        way. Both click through to the website.
        """
        img = self.FindName("brand_logo")
        if img is not None and os.path.isfile(LOGO_PATH):
            try:
                bmp = BitmapImage()
                bmp.BeginInit()
                bmp.CacheOption = BitmapCacheOption.OnLoad
                bmp.UriSource = Uri(LOGO_PATH, UriKind.Absolute)
                bmp.EndInit()
                bmp.Freeze()
                img.Source = bmp
                img.Cursor = Cursors.Hand
                img.ToolTip = "biminent.com"
                img.MouseLeftButtonDown += self._brand_logo_clicked
            except Exception:
                pass  # branding must never break a tool
        wordmark = self.FindName("brand_wordmark")
        if wordmark is not None:
            try:
                wordmark.Cursor = Cursors.Hand
                wordmark.ToolTip = "biminent.com"
                wordmark.MouseLeftButtonDown += self._brand_logo_clicked
            except Exception:
                pass

    def _brand_logo_clicked(self, sender, e):
        open_url(URL_WEBSITE)

    # ---- error reporting (full traceback to output, short line to status) ----

    def set_status(self, text):
        """Set the window's status line if it declares <... x:Name="status_text"/>."""
        ctrl = self.FindName("status_text")
        if ctrl is not None:
            ctrl.Text = text

    def report_errors(self, title):
        """Context manager: `with self.report_errors("Rename"): ...` - any error
        in the block is logged (full traceback) and shown in the status line,
        and the window stays alive."""
        return report.guard(title, self.set_status)

    def report_exception(self, title):
        """Call inside an `except` block: logs the traceback and shows a short
        message in the status line. Returns the short message."""
        short = report.log_traceback(title)
        self.set_status(short)
        return short

    # ---- chrome event handlers (wire these in XAML) ----

    def button_close(self, sender, e):
        self.Close()

    def header_drag(self, sender, e):
        if e.LeftButton == MouseButtonState.Pressed:
            self.DragMove()

    def open_link(self, sender, e):
        """Click handler for any control whose Tag holds a URL."""
        url = getattr(sender, "Tag", None)
        if url:
            open_url(str(url))

    def hyperlink_navigate(self, sender, e):
        """RequestNavigate handler for inline <Hyperlink> elements."""
        open_url(e.Uri.AbsoluteUri)
