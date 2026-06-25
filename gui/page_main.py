# Imports
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QTimer


# MainPage
class MainPage(QWidget):

    def __init__(self, stack_widget, register_idx, organize_idx):

        super().__init__()
        self.stack = stack_widget
        self.register_idx = register_idx
        self.organize_idx = organize_idx

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        label = QLabel("Select Menu")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        layout.addStretch()

        self.register_button = self.create_nav_button("Register", self.register_idx)
        self.organize_button = self.create_nav_button("Organize", self.organize_idx)

        layout.addWidget(self.register_button)
        layout.addWidget(self.organize_button)

    def create_nav_button(self, text, page_index):
        button = QPushButton(text)
        button.setMinimumHeight(50)
        button.setStyleSheet("font-size: 16px; font-weight: bold;")
        button.clicked.connect(lambda: self.on_button_clicked(page_index))
        return button

    def on_button_clicked(self, page_index):
        self.stack.setCurrentIndex(page_index)