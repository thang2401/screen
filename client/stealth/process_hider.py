import ctypes
import os
import sys
import logging

logger = logging.getLogger(__name__)

class ProcessHider:
    @staticmethod
    def hide_console():
        """Hides the current console window (Windows only)."""
        if os.name == 'nt':
            try:
                # 0 is SW_HIDE
                ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
                logger.info("Console window hidden successfully.")
            except Exception as e:
                logger.error(f"Failed to hide console window: {e}")

    @staticmethod
    def show_console():
        """Shows the current console window (Windows only)."""
        if os.name == 'nt':
            try:
                # 5 is SW_SHOW
                ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 5)
            except Exception as e:
                logger.error(f"Failed to show console window: {e}")
