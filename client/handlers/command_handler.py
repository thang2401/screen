"""
Command Handler - Xử lý các lệnh điều khiển từ server.
"""

import json
import logging
import subprocess
import sys
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CommandHandler:
    """
    Xử lý tất cả các lệnh từ server:
    - System commands (shutdown, restart, lock)
    - Monitoring commands (screenshot, process list)
    - File operations
    - Configuration updates
    """

    def __init__(self, client_service=None):
        self.client_service = client_service
        self.command_map = {
            'lock': self._cmd_lock,
            'unlock': self._cmd_unlock,
            'shutdown': self._cmd_shutdown,
            'restart': self._cmd_restart,
            'message': self._cmd_message,
            'ping': self._cmd_ping,
            'screenshot': self._cmd_screenshot,
            'process_list': self._cmd_process_list,
            'run_command': self._cmd_run_command,
            'update_config': self._cmd_update_config,
            'get_system_info': self._cmd_get_system_info,
            'open_url': self._cmd_open_url,
            'block_url': self._cmd_block_url,
            'mouse_move': self._cmd_mouse_move,
            'mouse_click': self._cmd_mouse_click,
            'mouse_scroll': self._cmd_mouse_scroll,
            'keyboard': self._cmd_keyboard,
            'key_press': self._cmd_keyboard,
            'type_text': self._cmd_type_text,
        }

    async def handle(self, command: str, params: Optional[Dict] = None) -> Dict:
        """Xử lý một lệnh."""
        handler = self.command_map.get(command)
        if not handler:
            logger.warning(f"Unknown command: {command}")
            return {'status': 'error', 'message': f'Unknown command: {command}'}

        try:
            result = await handler(**(params or {}))
            return {'status': 'success', 'data': result}
        except Exception as e:
            logger.error(f"Command {command} failed: {e}")
            return {'status': 'error', 'message': str(e)}

    async def _cmd_lock(self, **kwargs):
        """Khóa màn hình."""
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        return {'message': 'Screen locked'}

    async def _cmd_unlock(self, **kwargs):
        """Mở khóa (chỉ hoạt động với Windows Hello)."""
        return {'message': 'Unlock requires user interaction'}

    async def _cmd_shutdown(self, **kwargs):
        """Tắt máy."""
        delay = kwargs.get('delay', 5)
        if sys.platform == 'win32':
            subprocess.run(['shutdown', '/s', '/t', str(delay), '/c', 'Server requested shutdown'])
        elif sys.platform == 'linux':
            subprocess.run(['shutdown', '-h', f'+{delay // 60}'])
        return {'message': f'Shutting down in {delay}s'}

    async def _cmd_restart(self, **kwargs):
        """Khởi động lại."""
        delay = kwargs.get('delay', 5)
        if sys.platform == 'win32':
            subprocess.run(['shutdown', '/r', '/t', str(delay), '/c', 'Server requested restart'])
        return {'message': f'Restarting in {delay}s'}

    async def _cmd_message(self, **kwargs):
        """Hiển thị thông báo."""
        text = kwargs.get('text', '')
        title = kwargs.get('title', 'Message from Server')

        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, text, title, 0x40 | 0x1000)

        return {'message': f'Displayed: {text}'}

    async def _cmd_ping(self, **kwargs):
        """Ping response."""
        return {'message': 'pong', 'timestamp': __import__('time').time()}

    async def _cmd_screenshot(self, **kwargs):
        """Chụp ảnh màn hình ngay lập tức."""
        if self.client_service and self.client_service.capture:
            msg_type, data = self.client_service.capture.capture(force_full=True)
            if data:
                # Send immediately
                from core.protocol import Packet
                packet = Packet(msg_type, data, flags=4)  # Priority flag
                await self.client_service._send_packet(packet)
                return {'message': 'Screenshot sent', 'size': len(data)}
        return {'message': 'Screenshot failed'}

    async def _cmd_process_list(self, **kwargs):
        """Lấy danh sách tiến trình."""
        if sys.platform == 'win32':
            result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'],
                                    capture_output=True, text=True)
            processes = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.strip('"').split('","')
                    processes.append({
                        'name': parts[0] if len(parts) > 0 else '',
                        'pid': parts[1] if len(parts) > 1 else '',
                        'session': parts[2] if len(parts) > 2 else '',
                        'memory': parts[4] if len(parts) > 4 else '',
                    })
            return {'processes': processes[:100]}
        return {'processes': []}

    async def _cmd_run_command(self, **kwargs):
        """Chạy lệnh tùy chỉnh."""
        cmd = kwargs.get('command', '')
        if not cmd:
            return {'error': 'No command specified'}

        # Security check - only allow safe commands
        blacklist = ['format', 'del', 'rm', 'rd', 'format']
        if any(b in cmd.lower() for b in blacklist):
            return {'error': 'Command blocked for security'}

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return {
            'stdout': result.stdout[:5000],
            'stderr': result.stderr[:5000],
            'returncode': result.returncode,
        }

    async def _cmd_update_config(self, **kwargs):
        """Cập nhật cấu hình client."""
        if self.client_service:
            for key, value in kwargs.items():
                if hasattr(self.client_service.config, key):
                    setattr(self.client_service.config, key, value)
            return {'message': 'Config updated', 'updated': list(kwargs.keys())}
        return {'message': 'Config update failed'}

    async def _cmd_get_system_info(self, **kwargs):
        """Lấy thông tin hệ thống."""
        import platform
        import psutil

        return {
            'platform': platform.platform(),
            'processor': platform.processor(),
            'cpu_count': psutil.cpu_count(),
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory': psutil.virtual_memory()._asdict(),
            'disk': psutil.disk_usage('/')._asdict(),
            'boot_time': psutil.boot_time(),
            'hostname': platform.node(),
        }

    async def _cmd_open_url(self, **kwargs):
        """Mở URL trong browser."""
        url = kwargs.get('url', '')
        if url:
            import webbrowser
            webbrowser.open(url)
            return {'message': f'Opened: {url}'}
        return {'error': 'No URL provided'}

    async def _cmd_block_url(self, **kwargs):
        """Chặn URL (thêm vào hosts file)."""
        url = kwargs.get('url', '')
        if not url:
            return {'error': 'No URL provided'}

        try:
            if sys.platform == 'win32':
                hosts_path = r'C:\Windows\System32\drivers\etc\hosts'
            else:
                hosts_path = '/etc/hosts'

            with open(hosts_path, 'a') as f:
                f.write(f'\n127.0.0.1 {url}\n')

            return {'message': f'Blocked: {url}'}
        except Exception as e:
            return {'error': f'Block failed: {e}'}

    async def _cmd_mouse_move(self, **kwargs):
        """Di chuyển chuột dựa trên tọa độ %."""
        try:
            x_percent = kwargs.get('x_percent', 0.5)
            y_percent = kwargs.get('y_percent', 0.5)
            
            if sys.platform == 'win32':
                # TỐI ƯU 100% PING: Gắn trực tiếp vào Kernel C++ của Windows (0ms Latency)
                import ctypes
                user32 = ctypes.windll.user32
                sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
                mx = int(x_percent * sw)
                my = int(y_percent * sh)
                user32.SetCursorPos(mx, my)
            else:
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.PAUSE = 0
                sw, sh = pyautogui.size()
                mx = int(x_percent * sw)
                my = int(y_percent * sh)
                pyautogui.moveTo(mx, my, _pause=False)
                
            return {'message': 'Mouse moved'}
        except Exception as e:
            logger.error(f"Mouse move error: {e}")
            return {'error': str(e)}

    async def _cmd_mouse_click(self, **kwargs):
        """Click chuột dựa trên tọa độ %."""
        try:
            x_percent = kwargs.get('x_percent', 0.5)
            y_percent = kwargs.get('y_percent', 0.5)
            button = kwargs.get('button', 'left')
            pressed = kwargs.get('pressed', True)
            
            if sys.platform == 'win32':
                import ctypes
                user32 = ctypes.windll.user32
                sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
                mx = int(x_percent * sw)
                my = int(y_percent * sh)
                user32.SetCursorPos(mx, my)
                
                MOUSEEVENTF_LEFTDOWN = 0x0002
                MOUSEEVENTF_LEFTUP = 0x0004
                MOUSEEVENTF_RIGHTDOWN = 0x0008
                MOUSEEVENTF_RIGHTUP = 0x0010
                MOUSEEVENTF_MIDDLEDOWN = 0x0020
                MOUSEEVENTF_MIDDLEUP = 0x0040
                
                flags = 0
                if button == 'left':
                    flags = MOUSEEVENTF_LEFTDOWN if pressed else MOUSEEVENTF_LEFTUP
                elif button == 'right':
                    flags = MOUSEEVENTF_RIGHTDOWN if pressed else MOUSEEVENTF_RIGHTUP
                elif button == 'middle':
                    flags = MOUSEEVENTF_MIDDLEDOWN if pressed else MOUSEEVENTF_MIDDLEUP
                    
                if flags:
                    user32.mouse_event(flags, 0, 0, 0, 0)
            else:
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.PAUSE = 0
                sw, sh = pyautogui.size()
                mx = int(x_percent * sw)
                my = int(y_percent * sh)
                pyautogui.moveTo(mx, my, _pause=False)
                if pressed:
                    pyautogui.mouseDown(button=button, _pause=False)
                else:
                    pyautogui.mouseUp(button=button, _pause=False)
                
            return {'message': 'Mouse clicked'}
        except Exception as e:
            logger.error(f"Mouse click error: {e}")
            return {'error': str(e)}

    async def _cmd_mouse_scroll(self, **kwargs):
        """Cuộn chuột."""
        try:
            dy = kwargs.get('dy', 0)
            
            import sys
            if sys.platform == 'win32':
                import ctypes
                MOUSEEVENTF_WHEEL = 0x0800
                # Web browser deltaY is positive for scroll down, Windows requires negative for scroll down
                # Also we need to amplify the scroll amount to feel natural
                scroll_amount = -int(dy * 1.5) if dy != 0 else 0
                if scroll_amount != 0:
                    ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, scroll_amount, 0)
            else:
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.PAUSE = 0
                scroll_amount = -int(dy / 10) if dy != 0 else 0
                if scroll_amount != 0:
                    pyautogui.scroll(scroll_amount)
                
            return {'message': 'Mouse scrolled'}
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Mouse scroll error: {e}")
            return {'error': str(e)}

    async def _cmd_keyboard(self, **kwargs):
        """Nhấn/Nhả phím sử dụng ctypes SendInput (Chống lỗi Unikey và phân biệt hoa/thường)."""
        try:
            key_str = kwargs.get('key', '')
            is_pressed = kwargs.get('is_pressed', None)
            
            import sys
            if sys.platform != 'win32':
                return {'error': 'Only supported on Windows'}
                
            import ctypes
            from ctypes import wintypes
            
            ULONG_PTR = ctypes.c_size_t
            class KEYBDINPUT(ctypes.Structure):
                _fields_ = (("wVk", wintypes.WORD),
                            ("wScan", wintypes.WORD),
                            ("dwFlags", wintypes.DWORD),
                            ("time", wintypes.DWORD),
                            ("dwExtraInfo", ULONG_PTR))
            class MOUSEINPUT(ctypes.Structure):
                _fields_ = (("dx", wintypes.LONG),
                            ("dy", wintypes.LONG),
                            ("mouseData", wintypes.DWORD),
                            ("dwFlags", wintypes.DWORD),
                            ("time", wintypes.DWORD),
                            ("dwExtraInfo", ULONG_PTR))
            class HARDWAREINPUT(ctypes.Structure):
                _fields_ = (("uMsg", wintypes.DWORD),
                            ("wParamL", wintypes.WORD),
                            ("wParamH", wintypes.WORD))
            class INPUT_union(ctypes.Union):
                _fields_ = (("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT))
            class INPUT(ctypes.Structure):
                _fields_ = (("type", wintypes.DWORD), ("union", INPUT_union))
                
            INPUT_KEYBOARD = 1
            KEYEVENTF_EXTENDEDKEY = 0x0001
            KEYEVENTF_KEYUP = 0x0002
            KEYEVENTF_SCANCODE = 0x0008
            
            # Map tên phím gửi từ Server sang Virtual-Key Code (wVk)
            special_keys = {
                'enter': 0x0D, 'backspace': 0x08, 'tab': 0x09, 'esc': 0x1B,
                'shift': 0x10, 'ctrl': 0x11, 'alt': 0x12, 'win': 0x5B,
                'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
                'capslock': 0x14, 'delete': 0x2E, 'space': 0x20,
                'pageup': 0x21, 'pagedown': 0x22, 'home': 0x24, 'end': 0x23,
                'insert': 0x2D, 'apps': 0x5D
            }
            
            target_key = key_str.lower()
            vk = special_keys.get(target_key)
            
            if not vk and len(target_key) == 1:
                # Tìm wVk cho các phím in được (a-z, 0-9, dấu câu)
                vk_res = ctypes.windll.user32.VkKeyScanW(ord(key_str))
                if vk_res != -1:
                    vk = vk_res & 0xFF
                    
            if not vk:
                return {'error': f'Unsupported key: {key_str}'}
                
            # Sinh Hardware Scancode
            scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)
            
            # Thay vì chỉ dùng SCANCODE (có thể gây lỗi thiếu VK_CODE trên vài app), ta truyền luôn cả vk và scan
            # Bỏ cờ KEYEVENTF_SCANCODE để HĐH nhận đúng wVk, Unikey sẽ không nhảy chữ vì ta gõ từng phím cứng.
            flags = 0
            if vk in (0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5C, 0x5D):
                flags |= KEYEVENTF_EXTENDEDKEY
                
            inputs = []
            def add_input(up=False):
                inp = INPUT()
                inp.type = INPUT_KEYBOARD
                inp.union.ki.wVk = vk
                inp.union.ki.wScan = scan
                inp.union.ki.dwFlags = flags | (KEYEVENTF_KEYUP if up else 0)
                inputs.append(inp)
                
            if is_pressed is None:
                add_input(False)
                add_input(True)
            elif is_pressed:
                add_input(False)
            else:
                add_input(True)
                
            if inputs:
                nInputs = len(inputs)
                pInputs = (INPUT * nInputs)(*inputs)
                inserted = ctypes.windll.user32.SendInput(nInputs, pInputs, ctypes.sizeof(INPUT))
                if inserted == 0:
                    import logging
                    logging.getLogger(__name__).warning(f"SendInput failed for key {key_str}")
                    
            return {'message': f'Key {key_str} processed using SendInput'}
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Key event error: {e}")
            return {'error': str(e)}

    async def _cmd_type_text(self, **kwargs):
        """Gõ chuỗi văn bản Unicode (Hỗ trợ tiếng Việt từ Unikey Local)."""
        try:
            text = kwargs.get('text', '')
            if not text:
                return {'message': 'Empty text'}
                
            import sys
            if sys.platform == 'win32':
                import ctypes
                from ctypes import wintypes
                
                # Cấu trúc dành cho SendInput API chuẩn cho cả 32-bit và 64-bit
                ULONG_PTR = ctypes.c_size_t
                class KEYBDINPUT(ctypes.Structure):
                    _fields_ = (("wVk",         wintypes.WORD),
                                ("wScan",       wintypes.WORD),
                                ("dwFlags",     wintypes.DWORD),
                                ("time",        wintypes.DWORD),
                                ("dwExtraInfo", ULONG_PTR))
                                
                class HARDWAREINPUT(ctypes.Structure):
                    _fields_ = (("uMsg",    wintypes.DWORD),
                                ("wParamL", wintypes.WORD),
                                ("wParamH", wintypes.WORD))
                                
                class MOUSEINPUT(ctypes.Structure):
                    _fields_ = (("dx",          wintypes.LONG),
                                ("dy",          wintypes.LONG),
                                ("mouseData",   wintypes.DWORD),
                                ("dwFlags",     wintypes.DWORD),
                                ("time",        wintypes.DWORD),
                                ("dwExtraInfo", ULONG_PTR))

                class INPUT_union(ctypes.Union):
                    _fields_ = (("ki", KEYBDINPUT),
                                ("mi", MOUSEINPUT),
                                ("hi", HARDWAREINPUT))
                                
                class INPUT(ctypes.Structure):
                    _fields_ = (("type", wintypes.DWORD),
                                ("union", INPUT_union))
                                
                INPUT_KEYBOARD = 1
                KEYEVENTF_UNICODE = 0x0004
                KEYEVENTF_KEYUP = 0x0002
                
                # Cực kỳ quan trọng: Ép hệ điều hành nhả các phím Ctrl, Shift, Alt ra.
                # Vì khi Unikey dùng chế độ "Sử dụng clipboard cho unicode", nó lén gửi Ctrl+V.
                # Trình duyệt Web sẽ truyền phím Ctrl sang máy đích, làm máy đích bị đè phím Ctrl.
                # Khi ta bơm Unicode sang, máy đích tưởng đang bấm "Ctrl + Unicode" nên sẽ xoá mất chữ.
                modifiers = [0x11, 0x10, 0x12, 0x5B] # Ctrl, Shift, Alt, LWin
                for vk in modifiers:
                    ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
                
                inputs = []
                for char in text:
                    surrogates = char.encode('utf-16-le')
                    for i in range(0, len(surrogates), 2):
                        scan_code = int.from_bytes(surrogates[i:i+2], byteorder='little')
                        
                        # Down
                        inp_down = INPUT()
                        inp_down.type = INPUT_KEYBOARD
                        inp_down.union.ki.wVk = 0
                        inp_down.union.ki.wScan = scan_code
                        inp_down.union.ki.dwFlags = KEYEVENTF_UNICODE
                        inputs.append(inp_down)
                        
                        # Up
                        inp_up = INPUT()
                        inp_up.type = INPUT_KEYBOARD
                        inp_up.union.ki.wVk = 0
                        inp_up.union.ki.wScan = scan_code
                        inp_up.union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
                        inputs.append(inp_up)
                        
                if inputs:
                    nInputs = len(inputs)
                    pInputs = (INPUT * nInputs)(*inputs)
                    ctypes.windll.user32.SendInput(nInputs, pInputs, ctypes.sizeof(INPUT))
                return {'message': f'Typed {len(text)} characters'}
            else:
                import pyautogui
                pyautogui.typewrite(text)
                return {'message': f'Typed text via pyautogui'}
        except Exception as e:
            logger.error(f"Type text error: {e}")
            return {'error': str(e)}