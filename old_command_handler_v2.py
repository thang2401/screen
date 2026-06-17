"""
Command Handler - Xß╗¡ l├╜ c├íc lß╗çnh ─æiß╗üu khiß╗ân tß╗½ server.
"""

import json
import logging
import subprocess
import sys
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CommandHandler:
    """
    Xß╗¡ l├╜ tß║Ñt cß║ú c├íc lß╗çnh tß╗½ server:
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
        """Xß╗¡ l├╜ mß╗Öt lß╗çnh."""
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
        """Kh├│a m├án h├¼nh."""
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        return {'message': 'Screen locked'}

    async def _cmd_unlock(self, **kwargs):
        """Mß╗ƒ kh├│a (chß╗ë hoß║ít ─æß╗Öng vß╗¢i Windows Hello)."""
        return {'message': 'Unlock requires user interaction'}

    async def _cmd_shutdown(self, **kwargs):
        """Tß║»t m├íy."""
        delay = kwargs.get('delay', 5)
        if sys.platform == 'win32':
            subprocess.run(['shutdown', '/s', '/t', str(delay), '/c', 'Server requested shutdown'])
        elif sys.platform == 'linux':
            subprocess.run(['shutdown', '-h', f'+{delay // 60}'])
        return {'message': f'Shutting down in {delay}s'}

    async def _cmd_restart(self, **kwargs):
        """Khß╗ƒi ─æß╗Öng lß║íi."""
        delay = kwargs.get('delay', 5)
        if sys.platform == 'win32':
            subprocess.run(['shutdown', '/r', '/t', str(delay), '/c', 'Server requested restart'])
        return {'message': f'Restarting in {delay}s'}

    async def _cmd_message(self, **kwargs):
        """Hiß╗ân thß╗ï th├┤ng b├ío."""
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
        """Chß╗Ñp ß║únh m├án h├¼nh ngay lß║¡p tß╗⌐c."""
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
        """Lß║Ñy danh s├ích tiß║┐n tr├¼nh."""
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
        """Chß║íy lß╗çnh t├╣y chß╗ënh."""
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
        """Cß║¡p nhß║¡t cß║Ñu h├¼nh client."""
        if self.client_service:
            for key, value in kwargs.items():
                if hasattr(self.client_service.config, key):
                    setattr(self.client_service.config, key, value)
            return {'message': 'Config updated', 'updated': list(kwargs.keys())}
        return {'message': 'Config update failed'}

    async def _cmd_get_system_info(self, **kwargs):
        """Lß║Ñy th├┤ng tin hß╗ç thß╗æng."""
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
        """Mß╗ƒ URL trong browser."""
        url = kwargs.get('url', '')
        if url:
            import webbrowser
            webbrowser.open(url)
            return {'message': f'Opened: {url}'}
        return {'error': 'No URL provided'}

    async def _cmd_block_url(self, **kwargs):
        """Chß║╖n URL (th├¬m v├áo hosts file)."""
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
        """Di chuyß╗ân chuß╗Öt dß╗▒a tr├¬n tß╗ìa ─æß╗Ö %."""
        try:
            x_percent = kwargs.get('x_percent', 0.5)
            y_percent = kwargs.get('y_percent', 0.5)
            
            if sys.platform == 'win32':
                # Tß╗ÉI ╞»U 100% PING: Gß║»n trß╗▒c tiß║┐p v├áo Kernel C++ cß╗ºa Windows (0ms Latency)
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
        """Click chuß╗Öt dß╗▒a tr├¬n tß╗ìa ─æß╗Ö %."""
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
        """Cuß╗Ön chuß╗Öt."""
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
        """Nhß║Ñn/Nhß║ú ph├¡m."""
        try:
            key_str = kwargs.get('key', '')
            is_pressed = kwargs.get('is_pressed', None)
            
            import pyautogui
            pyautogui.FAILSAFE = False
            pyautogui.PAUSE = 0
            
            special_keys = {
                'Enter': 'enter', 'Backspace': 'backspace', 'Tab': 'tab', 'Escape': 'esc',
                'Shift': 'shift', 'Control': 'ctrl', 'Alt': 'alt', 'Meta': 'win',
                'ArrowUp': 'up', 'ArrowDown': 'down', 'ArrowLeft': 'left', 'ArrowRight': 'right',
                'CapsLock': 'capslock', 'Delete': 'delete', ' ': 'space'
            }
            
            target_key = special_keys.get(key_str, key_str.lower())
            valid_keys = pyautogui.KEY_NAMES
            if target_key in valid_keys or len(target_key) == 1:
                if is_pressed is None:
                    pyautogui.press(target_key, _pause=False)
                elif is_pressed:
                    pyautogui.keyDown(target_key, _pause=False)
                else:
                    pyautogui.keyUp(target_key, _pause=False)
                    
            return {'message': 'Key processed via pyautogui'}
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Key event error: {e}")
            return {'error': str(e)}

    async def _cmd_type_text(self, **kwargs):
        """G├╡ chuß╗ùi v─ân bß║ún Unicode (Hß╗ù trß╗ú tiß║┐ng Viß╗çt tß╗½ Unikey Local)."""
        try:
            text = kwargs.get('text', '')
            if not text:
                return {'message': 'Empty text'}
                
            import sys
            if sys.platform == 'win32':
                import ctypes
                from ctypes import wintypes
                
                # Cß║Ñu tr├║c d├ánh cho SendInput API chuß║⌐n cho cß║ú 32-bit v├á 64-bit
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
                
                # Cß╗▒c kß╗│ quan trß╗ìng: ├ëp hß╗ç ─æiß╗üu h├ánh nhß║ú c├íc ph├¡m Ctrl, Shift, Alt ra.
                # V├¼ khi Unikey d├╣ng chß║┐ ─æß╗Ö "Sß╗¡ dß╗Ñng clipboard cho unicode", n├│ l├⌐n gß╗¡i Ctrl+V.
                # Tr├¼nh duyß╗çt Web sß║╜ truyß╗ün ph├¡m Ctrl sang m├íy ─æ├¡ch, l├ám m├íy ─æ├¡ch bß╗ï ─æ├¿ ph├¡m Ctrl.
                # Khi ta b╞ím Unicode sang, m├íy ─æ├¡ch t╞░ß╗ƒng ─æang bß║Ñm "Ctrl + Unicode" n├¬n sß║╜ xo├í mß║Ñt chß╗».
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
