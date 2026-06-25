from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QPushButton, QStackedWidget)
from PySide6.QtCore import Qt, QTimer

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FileGraph")
        self.resize(700, 500)

        # 1. 화면 전환을 위한 스택 위젯 생성
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # 2. 페이지 생성 및 스택에 추가
        self.main_page = self.create_main_page()
        self.edit_page = self.create_edit_page()
        
        self.stack.addWidget(self.main_page) # 인덱스 0
        self.stack.addWidget(self.edit_page) # 인덱스 1

    def create_main_page(self):
        page = QWidget()
        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(30, 30, 30, 30)

        self.label = QLabel("Add files to connect", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.label)
        main_layout.addStretch()

        def create_button(text):
            btn = QPushButton(text, self)
            btn.setMinimumHeight(50)
            btn.setStyleSheet("font-size: 16px; font-weight: bold;")
            # Edit 버튼만 특별하게 이벤트 연결 분리
            if text == "Edit":
                btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
            else:
                btn.clicked.connect(self.on_button_clicked)
            return btn

        row1 = QHBoxLayout()
        row1.addWidget(create_button("Add"))
        row1.addWidget(create_button("Delete"))
        
        row2 = QHBoxLayout()
        row2.addWidget(create_button("Edit"))
        
        row3 = QHBoxLayout()
        row3.addWidget(create_button("Save"))
        row3.addWidget(create_button("Refresh"))

        main_layout.addLayout(row1)
        main_layout.addLayout(row2)
        main_layout.addLayout(row3)
        return page

    def create_edit_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        layout.addWidget(QLabel("여기는 Edit 페이지입니다! 🛠️", alignment=Qt.AlignmentFlag.AlignCenter))
        
        back_btn = QPushButton("뒤로가기")
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        layout.addWidget(back_btn)
        return page

    def on_button_clicked(self):
        clicked_button = self.sender()
        button_text = clicked_button.text()
        self.label.setText(f"'{button_text}' button clicked")
        clicked_button.setEnabled(False)
        QTimer.singleShot(2000, lambda: self.reset_ui(clicked_button))

    def reset_ui(self, button_to_enable):
        self.label.setText("Add files to connect")
        button_to_enable.setEnabled(True)