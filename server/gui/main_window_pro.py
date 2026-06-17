import sys
import numpy as np
import logging
import queue
import cv2
from typing import Dict
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QHBoxLayout, 
    QScrollArea, QVBoxLayout, QLabel, QPushButton, QMessageBox, QSizePolicy,
    QInputDialog, QLineEdit
)
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, Qt, QEvent
from PyQt6.QtGui import QImage, QPixmap, QKeyEvent, QMouseEvent
import json
import asyncio
import websockets
import requests
import threading
from server.gui.components.client_card_pro import ClientCardPro
from core.state import global_state

logger = logging.getLogger(__name__)

class NetworkBridgeThread(QThread):
    """
    Background thread reading from the Global Data Bus Queue and emitting signals to the Main UI Thread.
    """
    frame_received = pyqtSignal(str, np.ndarray)
    client_disconnected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        
    def run(self):
        self.running = True
        while self.running:
            try:
                # Chờ có frame mới
                client_id, frame = global_state.gui_queue.get(timeout=0.016) # 60FPS để khớp chuyển động khi xem video
                
                # Gom nhóm các frame mới nhất của từng máy con
                latest_frames = {client_id: frame}
                
                # Xả (drain) toàn bộ các frame đang chờ trong hàng đợi để hiển thị ngay lập tức
                # Tối ưu: Nếu có 10 frame của cùng 1 máy con ứ đọng, chỉ lấy frame cuối cùng để tránh làm đơ (lag) UI
                while not global_state.gui_queue.empty():
                    try:
                        cid, frm = global_state.gui_queue.get_nowait()
                        latest_frames[cid] = frm
                    except queue.Empty:
                        break
                        
                for cid, frm in latest_frames.items():
                    self._emit_frame(cid, frm)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Bridge error: {e}")
            
    def stop(self):
        self.running = False
        
    def _emit_frame(self, client_id, frame):
        if frame is None:
            self.client_disconnected.emit(client_id)
        else:
            self.frame_received.emit(client_id, frame)

class CommandSenderThread(QThread):
    """Thread chuyên dụng đảm bảo lệnh điều khiển gửi đi theo đúng thứ tự thời gian (FIFO)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = queue.Queue()
        self.running = False

    def run(self):
        self.running = True
        # Chuyển đổi HTTP Request sang WebSocket nội bộ để đạt tốc độ truyền Real-time (Ping ~0ms)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._websocket_loop())

    async def _websocket_loop(self):
        uri = "ws://127.0.0.1:8080/ws/admin"
        while self.running:
            try:
                async with websockets.connect(uri) as ws:
                    # Task đọc dữ liệu để thư viện tự phản hồi PING từ Server, tránh bị ngắt kết nối
                    async def receiver():
                        try:
                            while self.running:
                                await ws.recv()
                        except Exception:
                            pass
                    
                    recv_task = asyncio.create_task(receiver())
                    try:
                        while self.running:
                            if ws.closed:
                                break # Kết nối bị ngắt, thoát ngay để tạo kết nối lại
                            try:
                                client_id, command, params = self.queue.get_nowait()
                                try:
                                    await ws.send(json.dumps({
                                        "target_id": client_id,
                                        "action": command,
                                        "data": params
                                    }))
                                except Exception as e:
                                    break # Lỗi mạng khi đang gửi, ngắt để kết nối lại luôn
                            except queue.Empty:
                                await asyncio.sleep(0.005) # Quét hàng đợi siêu tốc 200 lần/giây
                    finally:
                        recv_task.cancel()
            except Exception as e:
                await asyncio.sleep(1)

    def stop(self):
        self.running = False

class MainWindowPro(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Screen Monitoring System Pro - Enterprise")
        self.resize(1280, 720)
        
        # Tính năng tàng hình: Chống hiệu ứng lặp màn hình vô tận khi test trên cùng 1 máy (Infinity Mirror)
        # Đồng thời tăng cường bảo mật, chống các phần mềm quay lén màn hình của Server.
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = int(self.winId())
                # WDA_EXCLUDEFROMCAPTURE = 0x00000011
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
            except Exception as e:
                logger.error(f"Could not hide window from capture: {e}")
        
        self.client_cards: Dict[str, ClientCardPro] = {}
        
        self.current_page = 0
        self.cards_per_page = 16 # 16 thẻ/trang (4 cột x 4 hàng)
        self.pressed_keys = set()
        
        self._init_ui()
        self.showMaximized() # Phóng to cửa sổ gốc để các màn hình con to hơn
        self._load_theme()
        
        # Setup Network Bridge connecting the global queue to the UI
        self.bridge = NetworkBridgeThread()
        self.bridge.frame_received.connect(self.on_frame_received)
        self.bridge.client_disconnected.connect(self.on_client_disconnected)
        self.bridge.start()
        
        # Khởi động luồng điều khiển
        self.command_sender = CommandSenderThread()
        self.command_sender.start()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Header
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(15)

        title_layout = QVBoxLayout()
        title = QLabel("Giám sát màn hình")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        warning_label = QLabel("⚠️ LƯU Ý: Vui lòng TẮT Unikey/EVKey trên máy của bạn (chuyển sang E) để gõ không bị lỗi tự xoá chữ!")
        warning_label.setStyleSheet("color: #ffc107; font-size: 13px; font-weight: bold;")
        title_layout.addWidget(title)
        title_layout.addWidget(warning_label)
        
        self.btn_online = QPushButton("Máy Online")
        self.btn_online.setStyleSheet("""
            QPushButton {
                background-color: #28a745; 
                color: white; 
                padding: 8px 15px; 
                border-radius: 5px; 
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self.btn_online.clicked.connect(self.show_online_clients)
        header_layout.addLayout(title_layout)
        header_layout.addWidget(self.btn_online)
        main_layout.addWidget(header_widget, alignment=Qt.AlignmentFlag.AlignCenter)

        # Scroll Area for Grid
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("border: none; background-color: transparent;")
        
        # Grid Container
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setContentsMargins(5, 5, 5, 5)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # Đặt 4 cột với tỷ lệ giãn (stretch) đều nhau
        for i in range(4): # Trở lại 4 cột
            self.grid_layout.setColumnStretch(i, 1)
        for i in range(4): # Đổi thành 4 hàng
            self.grid_layout.setRowStretch(i, 1) # Giữ cho 4 hàng luôn cao bằng nhau
        
        scroll_area.setWidget(self.grid_container)
        main_layout.addWidget(scroll_area)
        
        # Pagination controls (Thanh phân trang)
        self.pagination_layout = QHBoxLayout()
        
        self.btn_nav_style = """
            QPushButton {
                background-color: #17a2b8; 
                color: white; 
                border-radius: 4px; 
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #138496; }
            QPushButton:disabled { background-color: #6c757d; color: #ced4da; }
        """
        
        self.btn_page_style = """
            QPushButton {
                background-color: #6c757d; 
                color: white; 
                border-radius: 4px; 
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5a6268; }
            QPushButton:checked { background-color: #28a745; }
        """
        
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedSize(36, 32)
        self.btn_prev.setStyleSheet(self.btn_nav_style)
        self.btn_prev.clicked.connect(self.prev_page)
        
        self.page_buttons_layout = QHBoxLayout()
        self.page_buttons_layout.setSpacing(5)
        
        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedSize(36, 32)
        self.btn_next.setStyleSheet(self.btn_nav_style)
        self.btn_next.clicked.connect(self.next_page)
        
        self.pagination_layout.addStretch()
        self.pagination_layout.addWidget(self.btn_prev)
        self.pagination_layout.addLayout(self.page_buttons_layout)
        self.pagination_layout.addWidget(self.btn_next)
        self.pagination_layout.addStretch()
        main_layout.addLayout(self.pagination_layout)
        
        # Fullscreen Overlay Container (Nằm đè lên tất cả)
        self.fullscreen_container = QWidget(central_widget)
        self.fullscreen_container.setStyleSheet("background-color: #1e1e1e;")
        self.fullscreen_container.hide()
        
        # Ép giao diện tính toán lại kích thước sau khi thu nhỏ
        QApplication.processEvents()
        
        self.fs_layout = QVBoxLayout(self.fullscreen_container)
        self.fs_layout.setContentsMargins(0, 0, 0, 0) # Xóa viền để ảnh phóng to chiếm trọn 100% màn hình
        
        # Nút X nổi (Floating button) để đóng fullscreen
        self.btn_fs_close = QPushButton("❌", self.fullscreen_container)
        self.btn_fs_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fs_close.setStyleSheet("""
            QPushButton { background-color: rgba(220, 53, 69, 150); color: white; font-weight: bold; border-radius: 5px; font-size: 16px; border: none; }
            QPushButton:hover { background-color: rgba(220, 53, 69, 255); }
        """)
        self.btn_fs_close.setFixedSize(36, 36)
        self.btn_fs_close.clicked.connect(self.close_fullscreen)

    def _load_theme(self):
        try:
            with open("server/gui/resources/styles/dark_theme.qss", "r") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            logger.error(f"Could not load theme: {e}")

    def add_client(self, client_id: str):
        if client_id in self.client_cards:
            return
            
        card = ClientCardPro(client_id)
        card.double_clicked.connect(self.on_card_double_clicked)
        
        # Kích hoạt vẽ nền/viền (QSS) cho Component tuỳ chỉnh
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setStyleSheet("""
            ClientCardPro {
                border: 2px solid #787878;
                border-radius: 8px;
            }
        """)
        
        # Ép lề về 0 để ảnh tràn sát mép thẻ, tạo cảm giác Full Khung
        if card.layout():
            card.layout().setContentsMargins(0, 0, 0, 0)
            card.layout().setSpacing(0)
        
        # Xử lý các nhãn (QLabel) bên trong thẻ
        id_label = None
        status_label = None
        
        for label in card.findChildren(QLabel):
            if not label.text() and not hasattr(card, '_image_label'):
                # Tắt tự động co giãn của Qt để tránh làm méo tỉ lệ màn hình
                label.setScaledContents(False)
                # Kích hoạt nhận sự kiện chuột và phím
                label.setMouseTracking(True)
                label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                label.installEventFilter(self)
                # Dùng Ignored để chặn việc khung ảnh đòi kích thước gốc (1080p) phá nát Grid Layout
                label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
                label.setMinimumSize(10, 10)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                card._image_label = label  # Lưu tham chiếu để render tay sắc nét
                
                # CỰC KỲ QUAN TRỌNG: Ép layout nhường 100% không gian trống cho label ảnh để ảnh hiện to nhất có thể
                if card.layout():
                    card.layout().setStretchFactor(label, 1)
            else:
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if client_id in label.text():
                    id_label = label
                elif "Online" in label.text() or "Offline" in label.text():
                    status_label = label
                    
        # Gom chữ client_id và trạng thái lên cùng 1 dòng
        if id_label and status_label and id_label != status_label:
            id_label.setText(f"<b>{client_id}</b> | <span style='color: #28a745;'>Online</span>")
            id_label.setStyleSheet("font-size: 12px; margin: 5px 0px;")
            status_label.hide()
            card._id_label = id_label
            
        # Tạo nút Xem chi tiết (ẩn mặc định, hiện khi Hover)
        btn_details = QPushButton("Xem chi tiết", card)
        btn_details.setObjectName("btn_details")
        btn_details.setStyleSheet("""
            QPushButton { background-color: rgba(40, 167, 69, 220); color: white; padding: 10px 20px; border-radius: 5px; font-weight: bold; font-size: 10px; }
            QPushButton:hover { background-color: rgba(33, 136, 56, 255); }
        """)
        btn_details.hide()
        btn_details.clicked.connect(lambda _, cid=client_id: self.show_fullscreen(cid))
        
        card.installEventFilter(self)
        
        self.client_cards[client_id] = card
        
        self._rearrange_grid()

    @pyqtSlot(str, np.ndarray)
    def on_frame_received(self, client_id: str, frame: np.ndarray):
        """Called safely on the Main UI Thread when NetworkBridge emits a signal"""
        # Tránh tái tạo lại thẻ máy con nếu nhận được frame bị delay sau khi máy đã tắt
        client_state = global_state.client_states.get(client_id, {})
        if client_state.get("is_online") is False:
            return
            
        if client_id not in self.client_cards:
            self.add_client(client_id)
            
        card = self.client_cards[client_id]
        
        # TỐI ƯU HIỆU NĂNG: Chỉ vẽ lại hình ảnh nếu thẻ đó đang được hiển thị 
        # (nằm trong trang hiện tại) hoặc đang xem Fullscreen.
        if card.isVisible() or getattr(self, 'fullscreen_client_id', None) == client_id:
            if hasattr(card, 'update_frame') and frame is not None:
                card.frame_width = frame.shape[1]
                card.frame_height = frame.shape[0]
                card.update_frame(frame)

    @pyqtSlot(str)
    def on_card_double_clicked(self, client_id: str):
        self.show_fullscreen(client_id)

    @pyqtSlot(str)
    def on_client_disconnected(self, client_id: str):
        # TỰ ĐỘNG ĐÓNG FULLSCREEN: Ngăn giao diện kẹt màn hình đen khi máy mất kết nối
        if getattr(self, 'fullscreen_client_id', None) == client_id:
            self.close_fullscreen()
            
        if client_id in self.client_cards:
            card = self.client_cards.pop(client_id)
            self.grid_layout.removeWidget(card)
            card.hide()  # Ẩn thẻ khỏi giao diện ngay lập tức
            card.deleteLater()
            self._rearrange_grid()

    def _rearrange_grid(self):
        total_cards = len(self.client_cards)
        total_pages = max(1, (total_cards + self.cards_per_page - 1) // self.cards_per_page)
        
        if self.current_page >= total_pages:
            self.current_page = max(0, total_pages - 1)
            
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page < total_pages - 1)

        # Làm mới các nút số trang
        while self.page_buttons_layout.count():
            item = self.page_buttons_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        for i in range(total_pages):
            btn = QPushButton(str(i + 1))
            btn.setFixedSize(32, 32)
            btn.setCheckable(True)
            if i == self.current_page:
                btn.setChecked(True)
            btn.setStyleSheet(self.btn_page_style)
            # Note: Biến page=i giúp tránh lỗi closure vòng lặp của Python
            btn.clicked.connect(lambda checked, page=i: self.goto_page(page))
            self.page_buttons_layout.addWidget(btn)

        # Ẩn tất cả thẻ hiện tại
        for cid, card in self.client_cards.items():
            if getattr(self, 'fullscreen_client_id', None) == cid:
                continue
            card.hide()
            
        # Xóa các thẻ khỏi layout
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                self.grid_layout.removeWidget(item.widget())
                
        # Lấy danh sách client cho trang hiện tại
        all_clients = list(self.client_cards.items())
        start_idx = self.current_page * self.cards_per_page
        end_idx = start_idx + self.cards_per_page
        page_clients = all_clients[start_idx:end_idx]
        
        # Chèn lại các khung hình vào grid
        for idx, (cid, card) in enumerate(page_clients):
            if getattr(self, 'fullscreen_client_id', None) == cid:
                continue
            self.grid_layout.addWidget(card, idx // 4, idx % 4)
            card.show()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._rearrange_grid()
            
    def next_page(self):
        self.current_page += 1
        self._rearrange_grid()

    def goto_page(self, page):
        if self.current_page != page:
            self.current_page = page
            self._rearrange_grid()

    def show_fullscreen(self, client_id):
        # Chống lỗi thao tác nhanh: Đã mở rồi thì không mở lại, mở máy khác thì tự động đóng máy cũ
        if getattr(self, 'fullscreen_client_id', None) == client_id:
            return
        if getattr(self, 'fullscreen_client_id', None) is not None:
            self.close_fullscreen()
            
        if client_id not in self.client_cards:
            return
            
        self.fullscreen_client_id = client_id
        card = self.client_cards[client_id]
        
        # Xóa khỏi grid
        self.grid_layout.removeWidget(card)
        
        # Ẩn nút xem chi tiết khi đang ở chế độ Fullscreen
        btn = card.findChild(QPushButton, "btn_details")
        if btn:
            btn.hide()
            
        # Đưa thẻ màn hình vào giao diện Fullscreen (sử dụng addWidget thay vì insert để tránh lỗi kẹt layout)
        self.fs_layout.addWidget(card)
        
        # Ẩn text và xóa lề/viền để ảnh tràn 100% màn hình
        if card.layout():
            card.layout().setContentsMargins(0, 0, 0, 0)
            card.layout().setSpacing(0)
            
        card.setStyleSheet("ClientCardPro { border: none; background-color: black; }")
        if hasattr(card, '_id_label') and card._id_label:
            card._id_label.hide()
        
        # Gỡ bỏ mọi giới hạn kích thước cũ và ép giãn nở tối đa
        card.setMaximumSize(16777215, 16777215)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card.show()
        
        if hasattr(card, '_image_label'):
            card._image_label.setFocus()
        
        self.fullscreen_container.setGeometry(0, 0, self.width(), self.height())
        self.btn_fs_close.move(self.width() - self.btn_fs_close.width() - 20, 20)
        self.btn_fs_close.raise_()
        self.fullscreen_container.show()
        self.fullscreen_container.raise_()
        
        # Ép giao diện tính toán lại kích thước lập tức để frame tiếp theo không bị lấy sai tỷ lệ
        QApplication.processEvents()

    def close_fullscreen(self):
        client_id = getattr(self, 'fullscreen_client_id', None)
        if client_id is None:
            return
            
        card = self.client_cards.get(client_id)
        
        # Quan trọng: Phải xóa trạng thái Fullscreen TRƯỚC KHI gọi hàm _rearrange_grid
        self.fullscreen_client_id = None
        
        if card:
            self.fs_layout.removeWidget(card)
            # Khôi phục lại kích thước hiển thị lưới mặc định
            card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            
            # Khôi phục lại lề, viền và chữ khi thu nhỏ về lưới
            if card.layout():
                card.layout().setContentsMargins(0, 0, 0, 0)
                card.layout().setSpacing(0)
                
            card.setStyleSheet("ClientCardPro { border: 2px solid #787878; border-radius: 8px; }")
            
            if hasattr(card, '_id_label') and card._id_label:
                card._id_label.show()
                
            self._rearrange_grid()
            
        self.fullscreen_container.hide()

    def _get_normalized_coordinates(self, event, qlabel_obj, card_obj):
        """
        Tính toán tọa độ chuột chuẩn hóa (dưới dạng %) trên một hình ảnh có thể bị letterbox.
        Logic này tương đương với hàm getNormalizedCoordinates bên phía Javascript.
        """
        lbl_w, lbl_h = qlabel_obj.width(), qlabel_obj.height()
        if lbl_w <= 0 or lbl_h <= 0:
            return None

        orig_w = getattr(card_obj, 'frame_width', 1920)
        orig_h = getattr(card_obj, 'frame_height', 1080)

        element_ratio = lbl_w / lbl_h
        img_ratio = orig_w / orig_h

        offset_x, offset_y = 0, 0

        if element_ratio > img_ratio:  # Viền đen ở hai bên (trái, phải)
            rendered_height = lbl_h
            rendered_width = lbl_h * img_ratio
            offset_x = (lbl_w - rendered_width) / 2
        else:  # Viền đen ở trên và dưới
            rendered_width = lbl_w
            rendered_height = lbl_w / img_ratio
            offset_y = (lbl_h - rendered_height) / 2

        px, py = event.pos().x(), event.pos().y()
        x = px - offset_x
        y = py - offset_y

        if x < 0 or y < 0 or x > rendered_width or y > rendered_height:
            return None # Click vào viền đen, bỏ qua
        return {'x_percent': max(0, min(1, x / rendered_width)), 'y_percent': max(0, min(1, y / rendered_height))}

    def send_remote_command(self, client_id, command, params):
        # Đưa lệnh vào hàng đợi để gửi tuần tự chống kẹt phím
        if hasattr(self, 'command_sender'):
            self.command_sender.queue.put((client_id, command, params))

    def eventFilter(self, obj, event):
        fs_client_id = getattr(self, 'fullscreen_client_id', None)
        
        # Capture control events on the expanded image label
        if fs_client_id:
            card = self.client_cards.get(fs_client_id)
            if card and hasattr(card, '_image_label') and obj == card._image_label:
                # --- SỬA LỖI ĐIỀU KHIỂN CHUỘT ---
                mouse_events = (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick)
                if event.type() in mouse_events:
                    norm_coords = self._get_normalized_coordinates(event, obj, card)
                    if not norm_coords: return True # Bỏ qua nếu click ra ngoài ảnh

                    if event.type() == QEvent.Type.MouseMove:
                        import time
                        current_time = time.time()
                        if current_time - getattr(self, 'last_mouse_move', 0) < 0.033: # 30 FPS
                            return True
                        self.last_mouse_move = current_time
                        self.send_remote_command(fs_client_id, 'mouse_move', norm_coords)
                    else: # Press, Release, DblClick
                        button = 'left' if event.button() == Qt.MouseButton.LeftButton else ('right' if event.button() == Qt.MouseButton.RightButton else 'middle')
                        is_pressed = event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick)
                        self.send_remote_command(fs_client_id, 'mouse_click', {
                            'button': button, 'pressed': is_pressed, **norm_coords
                        })
                    return True
                
                # --- BỔ SUNG LĂN CHUỘT ---
                elif event.type() == QEvent.Type.Wheel:
                    import time
                    current_time = time.time()
                    if current_time - getattr(self, 'last_scroll', 0) < 0.05: # Chống spam scroll
                        return True
                    self.last_scroll = current_time
                    # angleDelta().y() trả về giá trị dương khi cuộn lên, âm khi cuộn xuống
                    self.send_remote_command(fs_client_id, 'mouse_scroll', {'dy': event.angleDelta().y()})
                    return True
                
                elif event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                    # --- SỬA LỖI GIỮ PHÍM ---
                    if event.isAutoRepeat():
                        # Cho phép giữ phím lặp lại với Backspace và phím điều hướng
                        if event.key() not in (Qt.Key.Key_Backspace, Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
                            return True

                    key_code = event.key()
                    key_map = {
                        Qt.Key.Key_Return: 'enter', Qt.Key.Key_Enter: 'enter', Qt.Key.Key_Space: 'space',
                        Qt.Key.Key_Backspace: 'backspace', Qt.Key.Key_Escape: 'esc', Qt.Key.Key_Tab: 'tab',
                        Qt.Key.Key_Up: 'up', Qt.Key.Key_Down: 'down', Qt.Key.Key_Left: 'left', Qt.Key.Key_Right: 'right',
                        Qt.Key.Key_Shift: 'shift', Qt.Key.Key_Control: 'ctrl', Qt.Key.Key_Alt: 'alt', Qt.Key.Key_Meta: 'win',
                        Qt.Key.Key_CapsLock: 'capslock', Qt.Key.Key_Delete: 'delete'
                    }
                    
                    key_text = key_map.get(key_code)
                    
                    if not key_text:
                        # Chuẩn hóa phím chữ/số cơ bản thành chữ thường (lowercase)
                        # Tránh lỗi "double shift" khi client nhận chữ IN HOA ('A') kết hợp với phím Shift đang giữ
                        if 32 <= key_code <= 126:
                            try:
                                key_text = chr(key_code).lower()
                            except ValueError:
                                pass
                        else:
                            key_text = event.text().lower() if event.text() else ""
                        
                    if key_text:
                        is_pressed = event.type() == QEvent.Type.KeyPress
                        
                        if is_pressed:
                            if not event.isAutoRepeat():
                                if key_text in self.pressed_keys:
                                    return True # Chống dội phím
                                self.pressed_keys.add(key_text)
                            self.send_remote_command(fs_client_id, 'key_press', {'key': key_text, 'is_pressed': True})
                        else:
                            if key_text in self.pressed_keys:
                                self.pressed_keys.remove(key_text)
                            # Luôn gửi nhả phím để tránh kẹt phím gây loạn chữ
                            self.send_remote_command(fs_client_id, 'key_press', {'key': key_text, 'is_pressed': False})
                    return True

        if hasattr(self, 'client_cards') and obj in self.client_cards.values():
            if getattr(self, 'fullscreen_client_id', None) and self.client_cards.get(self.fullscreen_client_id) == obj:
                return super().eventFilter(obj, event)
                
            if event.type() == QEvent.Type.Enter:
                btn = obj.findChild(QPushButton, "btn_details")
                if btn:
                    btn.move(obj.width() // 2 - btn.width() // 2, obj.height() // 2 - btn.height() // 2)
                    btn.show()
            elif event.type() == QEvent.Type.Leave:
                btn = obj.findChild(QPushButton, "btn_details")
                if btn:
                    btn.hide()
            elif event.type() == QEvent.Type.Resize:
                btn = obj.findChild(QPushButton, "btn_details")
                if btn and btn.isVisible():
                    btn.move(obj.width() // 2 - btn.width() // 2, obj.height() // 2 - btn.height() // 2)
        return super().eventFilter(obj, event)

    def show_online_clients(self):
        clients = list(self.client_cards.keys())
        if not clients:
            QMessageBox.information(self, "Máy Online", "Hiện không có máy nào đang kết nối.")
        else:
            html = "<h3>Các máy đang online:</h3><table border='1' cellspacing='0' cellpadding='8' style='border-collapse: collapse; border-color: gray;'>"
            chunks = [clients[i:i + 4] for i in range(0, len(clients), 4)]
            for chunk in chunks:
                html += "<tr>"
                for cid in chunk:
                    html += f"<td width='120'>🎮 {cid}</td>"
                for _ in range(4 - len(chunk)):
                    html += "<td width='120'></td>"
                html += "</tr>"
            html += "</table>"
            
            QMessageBox.information(self, "Máy Online", html)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, 'fullscreen_container') and self.fullscreen_container.isVisible():
            self.fullscreen_container.setGeometry(0, 0, self.width(), self.height())
            if hasattr(self, 'btn_fs_close'):
                self.btn_fs_close.move(self.width() - self.btn_fs_close.width() - 20, 20)

    def closeEvent(self, event):
        password, ok = QInputDialog.getText(
            self, 
            "Xác thực bảo mật", 
            "Vui lòng nhập mật khẩu để tắt Server:", 
            QLineEdit.EchoMode.Password
        )
        
        if ok and password == "thang2414":
            self.bridge.stop()
            self.bridge.wait()
            if hasattr(self, 'command_sender'):
                self.command_sender.stop()
                self.command_sender.wait()
            super().closeEvent(event)
        else:
            if ok:
                QMessageBox.warning(self, "Lỗi bảo mật", "Mật khẩu không chính xác. Không thể tắt Server!")
            event.ignore()
