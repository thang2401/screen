        """Nhn/Nh phm."""
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
        """G chui vn bn Unicode (H tr ting Vit t Unikey Local)."""
        try:
            text = kwargs.get('text', '')
            if not text:
                return {'message': 'Empty text'}
                
            import sys
            if sys.platform == 'win32':
                import ctypes
                from ctypes import wintypes
                
                # Cu trc dnh cho SendInput API chun cho c 32-bit v 64-bit
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
                
                # Cc k quan trng: p h iu hnh nh cc phm Ctrl, Shift, Alt ra.
                # V khi Unikey dng ch  "S dng clipboard cho unicode", n ln gi Ctrl+V.
                # Trnh duyt Web s truyn phm Ctrl sang my ch, lm my ch b  phm Ctrl.
                # Khi ta bm Unicode sang, my ch tng ang bm "Ctrl + Unicode" nn s xo mt ch.
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
