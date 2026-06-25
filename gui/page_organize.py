# Imports
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog
from PySide6.QtCore import Qt


# OrganizePage
class OrganizePage(QWidget):

    def __init__(self, stack_widget, main_idx):

        super().__init__()
        self.stack = stack_widget
        self.main_idx = main_idx

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        layout.addWidget(
            QLabel("Organize File/Folder Page", alignment=Qt.AlignmentFlag.AlignCenter)
        )

        self.folder_label = QLabel("선택된 폴더 없음")
        self.folder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.folder_label)

        layout.addStretch()

        upload_btn = QPushButton("Upload Folder")
        upload_btn.setMinimumHeight(50)
        upload_btn.clicked.connect(self.upload_folder)
        layout.addWidget(upload_btn)

        back_button = QPushButton("Back")
        back_button.clicked.connect(lambda: self.stack.setCurrentIndex(self.main_idx))
        layout.addWidget(back_button)

    def upload_folder(self):

        folder_path = QFileDialog.getExistingDirectory(self, "폴더 선택", "")
        
        if folder_path:
            self.folder_label.setText(f"[폴더 선택됨]\n{folder_path}")