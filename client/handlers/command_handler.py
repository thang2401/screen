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
        """Nhấn/Nhả phím sử dụng ctypes SendInput (Hỗ trợ tổ hợp phím Ctrl/Alt/Shift)."""
        try:
            key_str = kwargs.get('key', '')
            code_str = kwargs.get('code', '')
            is_pressed = kwargs.get('is_pressed', None)
            mod_ctrl  = kwargs.get('ctrl', False)
            mod_alt   = kwargs.get('alt', False)
            mod_shift = kwargs.get('shift', False)
            mod_meta  = kwargs.get('meta', False)
            
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
            
            # Map JS event.code -> Windows Virtual-Key Code (wVk)
            VK_MAP = {
                'Backspace': 0x08, 'Tab': 0x09, 'Enter': 0x0D, 'NumpadEnter': 0x0D,
                'ShiftLeft': 0xA0, 'ShiftRight': 0xA1, 'ControlLeft': 0xA2, 'ControlRight': 0xA3,
                'AltLeft': 0xA4, 'AltRight': 0xA5, 'Pause': 0x13, 'CapsLock': 0x14,
                'Escape': 0x1B, 'Space': 0x20, 'PageUp': 0x21, 'PageDown': 0x22,
                'End': 0x23, 'Home': 0x24, 'ArrowLeft': 0x25, 'ArrowUp': 0x26,
                'ArrowRight': 0x27, 'ArrowDown': 0x28, 'PrintScreen': 0x2C,
                'Insert': 0x2D, 'Delete': 0x2E,
                'Digit0': 0x30, 'Digit1': 0x31, 'Digit2': 0x32, 'Digit3': 0x33,
                'Digit4': 0x34, 'Digit5': 0x35, 'Digit6': 0x36, 'Digit7': 0x37,
                'Digit8': 0x38, 'Digit9': 0x39,
                'KeyA': 0x41, 'KeyB': 0x42, 'KeyC': 0x43, 'KeyD': 0x44, 'KeyE': 0x45,
                'KeyF': 0x46, 'KeyG': 0x47, 'KeyH': 0x48, 'KeyI': 0x49, 'KeyJ': 0x4A,
                'KeyK': 0x4B, 'KeyL': 0x4C, 'KeyM': 0x4D, 'KeyN': 0x4E, 'KeyO': 0x4F,
                'KeyP': 0x50, 'KeyQ': 0x51, 'KeyR': 0x52, 'KeyS': 0x53, 'KeyT': 0x54,
                'KeyU': 0x55, 'KeyV': 0x56, 'KeyW': 0x57, 'KeyX': 0x58, 'KeyY': 0x59, 'KeyZ': 0x5A,
                'MetaLeft': 0x5B, 'MetaRight': 0x5C, 'ContextMenu': 0x5D,
                'Numpad0': 0x60, 'Numpad1': 0x61, 'Numpad2': 0x62, 'Numpad3': 0x63,
                'Numpad4': 0x64, 'Numpad5': 0x65, 'Numpad6': 0x66, 'Numpad7': 0x67,
                'Numpad8': 0x68, 'Numpad9': 0x69, 'NumpadMultiply': 0x6A,
                'NumpadAdd': 0x6B, 'NumpadSubtract': 0x6D, 'NumpadDecimal': 0x6E,
                'NumpadDivide': 0x6F,
                'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73, 'F5': 0x74, 'F6': 0x75,
                'F7': 0x76, 'F8': 0x77, 'F9': 0x78, 'F10': 0x79, 'F11': 0x7A, 'F12': 0x7B,
                'NumLock': 0x90, 'ScrollLock': 0x91,
                'Semicolon': 0xBA, 'Equal': 0xBB, 'Comma': 0xBC, 'Minus': 0xBD,
                'Period': 0xBE, 'Slash': 0xBF, 'Backquote': 0xC0,
                'BracketLeft': 0xDB, 'Backslash': 0xDC, 'BracketRight': 0xDD, 'Quote': 0xDE
            }
            
            vk = VK_MAP.get(code_str)
            
            if not vk and len(key_str) == 1:
                # Fallback cho phím không nằm trong code map
                vk_res = ctypes.windll.user32.VkKeyScanW(ord(key_str))
                if vk_res != -1:
                    vk = vk_res & 0xFF
                    
            if not vk:
                return {'error': f'Unsupported key/code: {key_str}/{code_str}'}

            # Phím nào cần cờ EXTENDEDKEY
            EXTENDED_VKS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
                            0x2D, 0x2E, 0x5B, 0x5C, 0x5D, 0x6F, 0xA3, 0xA5}

            def make_input(vk_code, up=False):
                scan = ctypes.windll.user32.MapVirtualKeyW(vk_code, 0)
                flags = KEYEVENTF_KEYUP if up else 0
                if vk_code in EXTENDED_VKS or code_str == 'NumpadEnter':
                    flags |= KEYEVENTF_EXTENDEDKEY
                inp = INPUT()
                inp.type = INPUT_KEYBOARD
                inp.union.ki.wVk = vk_code
                inp.union.ki.wScan = scan
                inp.union.ki.dwFlags = flags
                return inp

            inputs = []

            if is_pressed:
                # Nhấn xuống: modifiers trước rồi mới đến phím chính
                if mod_ctrl:  inputs.append(make_input(0xA2, False))  # ControlLeft
                if mod_alt:   inputs.append(make_input(0xA4, False))  # AltLeft
                if mod_shift: inputs.append(make_input(0xA0, False))  # ShiftLeft
                if mod_meta:  inputs.append(make_input(0x5B, False))  # MetaLeft
                # Chỉ gửi phím chính nếu nó không được gửi riêng như modifier
                if vk not in (0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0x5B, 0x5C):
                    inputs.append(make_input(vk, False))
                    inputs.append(make_input(vk, True))
                    # Nhả modifiers sau khi phiên bấm hoàn tất
                    if mod_shift: inputs.append(make_input(0xA0, True))
                    if mod_alt:   inputs.append(make_input(0xA4, True))
                    if mod_ctrl:  inputs.append(make_input(0xA2, True))
                    if mod_meta:  inputs.append(make_input(0x5B, True))
                else:
                    # Đây chính là phím modifier được nhấn, chỉ gửi keydown
                    inputs.append(make_input(vk, False))
            else:
                # Nhả phím (keyup) – chỉ gửi keyup cho chính nó
                inputs.append(make_input(vk, True))

            if inputs:
                nInputs = len(inputs)
                pInputs = (INPUT * nInputs)(*inputs)
                inserted = ctypes.windll.user32.SendInput(nInputs, pInputs, ctypes.sizeof(INPUT))
                if inserted == 0:
                    logger.warning(f"SendInput failed for key {key_str}/{code_str}")
                    
            return {'message': f'Key {code_str or key_str} processed using SendInput'}
        except Exception as e:
            logger.error(f"Key event error: {e}")
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