from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
)

from ui.dashboard import Dashboard
from ui.pdf_page import PdfPage

from ui.widgets.sidebar import Sidebar
from ui.widgets.topbar import TopBar


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("MarkaAI")
        self.resize(1400, 850)

        self.build_ui()

    def build_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Sol Menü
        self.sidebar = Sidebar()

        # Sağ Alan
        right_widget = QWidget()

        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(20)

        # Üst Menü
        self.topbar = TopBar()

        # Sayfalar
        self.pages = QStackedWidget()

        # Sayfalar
        self.home_page = Dashboard()
        self.home_page.page_requested.connect(self.change_page)
        self.pdf_page = PdfPage()

        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.pdf_page)

        right_layout.addWidget(self.topbar)
        right_layout.addWidget(self.pages)

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(right_widget)

        self.sidebar.page_changed.connect(self.change_page)

    def change_page(self, page):

        if page == "Dashboard":
            self.pages.setCurrentWidget(self.home_page)

        elif page == "PDF Fatura":
            self.pages.setCurrentWidget(self.pdf_page)