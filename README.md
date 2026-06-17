Tìm IP của Máy Chủ:
Trên Máy Chủ, nhấn tổ hợp phím Win + R, gõ cmd rồi Enter.
Gõ lệnh ipconfig và nhấn Enter.
Tìm dòng IPv4 Address. Giả sử IP của bạn là 192.168.1.45. Hãy ghi nhớ IP này!
Cấu hình Tường Lửa (Firewall):
Chạy file Server bằng lệnh python run_server.py.
Nếu Windows hiện lên bảng thông báo bảo mật Windows Security Alert, bạn BẮT BUỘC phải tick chọn vào BẢN CẢ 2 Ô Private networks và Public networks, sau đó bấm Allow access.
(Nếu không làm bước này, máy chủ sẽ chặn luồng gửi video của máy con).
Bước 3: Triển khai trên Máy Con (Client)
Chuẩn bị: Copy toàn bộ thư mục code của bạn (screen-monitoring-system-pro) sang máy con và cài đặt thư viện bằng pip install -r requirements.txt giống như đã làm ở máy chủ.

cấu hình hai ,máy con :https://login.tailscale.com/admin/welcome
login cùng tài khoản với admin để cấu hình mạng 
Chạy Client kết nối với Server: Mở Terminal/CMD trên Máy Con, di chuyển vào thư mục code và chạy lệnh với cấu trúc:
 máy con : python run_client.py <TÊN_MÁY> 100.90.9.76
Ví dụ:

bash
python run_client.py MAY_01 100.90.9.76
Lúc này, Máy con MAY_01 sẽ lập tức kết nối và truyền hình ảnh Full HD siêu mượt lên giao diện của Máy chủ.

💡 Mẹo Pro: Cách chạy ẩn Client không hiện cửa sổ đen
Khi chạy thật, bạn không muốn người dùng Máy Con nhìn thấy cái màn hình đen CMD đang chạy chữ. Để làm Client chạy ngầm hoàn toàn trong nền hệ thống, bạn hãy sử dụng pythonw thay vì python.

Cách làm: Tạo một file .bat (ví dụ start_client.bat) trên Máy Con với nội dung sau:

bat
@echo off
cd "D:\đường_dẫn_tới_thư_mục_chứa_code"
start pythonw run_client.py MAY_01 100.90.9.76
exit
Khi người dùng (hoặc hệ thống lúc khởi động) click đúp vào file start_client.bat này, nó sẽ âm thầm bật Client lên chạy nền mà không để lại bất kỳ dấu vết cửa sổ nào. Để tắt nó, bạn sẽ cần vào Task Manager tìm tiến trình pythonw.exe rồi End Task