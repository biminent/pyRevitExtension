# -*- coding: utf-8 -*-
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
