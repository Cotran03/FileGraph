# Imports
from PySide6.QtWidgets import QMainWindow, QStackedWidget
from gui.page_main import MainPage
from gui.page_register import RegisterPage
from gui.page_organize import OrganizePage


# MainWindow
class MainWindow(QMainWindow):

    # Page Index
    MAIN_PAGE = 0
    REGISTER_PAGE = 1
    ORGANIZE_PAGE = 2

    def __init__(self):
        
        super().__init__()

        self.setWindowTitle("FileGraph")
        self.resize(700, 500)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.main_page = MainPage(self.stack, self.REGISTER_PAGE, self.ORGANIZE_PAGE)
        self.register_page = RegisterPage(self.stack, self.MAIN_PAGE)
        self.organize_page = OrganizePage(self.stack, self.MAIN_PAGE)

        self.stack.addWidget(self.main_page)
        self.stack.addWidget(self.register_page)
        self.stack.addWidget(self.organize_page)