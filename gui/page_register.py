# Imports
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog
from PySide6.QtCore import Qt


# RegisterPage
class RegisterPage(QWidget):

    def __init__(self, stack_widget, main_idx):

        super().__init__()
        self.stack = stack_widget
        self.main_idx = main_idx

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        layout.addWidget(
            QLabel("Register Relationship Page", alignment=Qt.AlignmentFlag.AlignCenter)
        )
        
        self.path_label = QLabel("선택된 파일/폴더 없음")
        self.path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.path_label)
        
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        file_btn = QPushButton("Upload File")
        file_btn.setMinimumHeight(50)
        file_btn.clicked.connect(self.upload_file)
        btn_layout.addWidget(file_btn)

        folder_btn = QPushButton("Upload Folder")
        folder_btn.setMinimumHeight(50)
        folder_btn.clicked.connect(self.upload_folder)
        btn_layout.addWidget(folder_btn)

        layout.addLayout(btn_layout)

        back_button = QPushButton("Back")
        back_button.clicked.connect(lambda: self.stack.setCurrentIndex(self.main_idx))
        layout.addWidget(back_button)

    def upload_file(self):

        file_path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", "All Files (*)")

        if file_path:
            self.path_label.setText(f"[파일 선택됨]\n{file_path}")

    def upload_folder(self):

        folder_path = QFileDialog.getExistingDirectory(self, "폴더 선택", "")
        
        if folder_path:
            self.path_label.setText(f"[폴더 선택됨]\n{folder_path}")