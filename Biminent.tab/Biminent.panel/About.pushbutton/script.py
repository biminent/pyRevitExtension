# -*- coding: utf-8 -*-
__title__   = "About\nBiminent"
__doc__     = """About Biminent Tools.

Free productivity tools for Revit by Biminent.
Visit biminent.com for our professional products."""
__author__  = "Biminent"
__helpurl__ = "https://biminent.com"

import os
from datetime import datetime

from biminent import VERSION
from biminent.ui import BiminentWindow


class AboutWindow(BiminentWindow):
    def __init__(self):
        xaml = os.path.join(os.path.dirname(__file__), "AboutWindow.xaml")
        BiminentWindow.__init__(self, xaml)
        self.footer_version.Text = "Biminent Tools v{}".format(VERSION)
        self.footer_copyright.Text = u"© {} Biminent".format(datetime.now().year)


if __name__ == "__main__":
    AboutWindow().ShowDialog()
