import cv2
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt, pyqtSignal

class ClientCardPro(QFrame):
    # Signals can be used if we need to bubble events up (e.g. double click)
    double_clicked = pyqtSignal(str)

    def __init__(self, client_id: str, parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.setObjectName("clientCard")
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header layout (Name and Status)
        self.name_label = QLabel(self.client_id)
        self.name_label.setObjectName("clientName")
        
        self.status_label = QLabel("Online")
        self.status_label.setObjectName("clientStatusOnline")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Image Display
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(320, 180) # 16:9 ratio
        self.video_label.setStyleSheet("background-color: black;")
        
        layout.addWidget(self.name_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.video_label)
        
        self.setLayout(layout)

    def update_frame(self, frame: np.ndarray):
        if frame is None or frame.size == 0:
            return

        # Convert cv2 BGR to RGB for Qt
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        
        qt_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        # Scale keeping aspect ratio
        pixmap = QPixmap.fromImage(qt_img)
        
        # Determine actual rendering size, avoid scaling to 0x0
        label_size = self.video_label.size()
        if label_size.width() > 10 and label_size.height() > 10:
            # Use IgnoreAspectRatio to fill the whole label, avoiding borders/smaller image
            scaled_pixmap = pixmap.scaled(label_size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.video_label.setPixmap(scaled_pixmap)
        else:
            self.video_label.setPixmap(pixmap)

    def set_offline(self):
        self.status_label.setText("Offline")
        self.status_label.setObjectName("clientStatusOffline")
        self.video_label.clear()
        self.video_label.setText("No Signal")
        # Force style re-eval
        self.style().unpolish(self.status_label)
        self.style().polish(self.status_label)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.client_id)
        super().mouseDoubleClickEvent(event)
