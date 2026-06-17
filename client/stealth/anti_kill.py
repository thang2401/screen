import os
import sys
import time
import subprocess
import psutil
import logging
from multiprocessing import Process

logger = logging.getLogger(__name__)

class AntiKillWatchdog:
    """
    Dual-process architecture:
    Main App spawns a Watchdog process.
    Watchdog monitors Main App. If Main App dies, Watchdog restarts it.
    Main App monitors Watchdog. If Watchdog dies, Main App restarts it.
    """
    def __init__(self, target_pid: int, executable_path: str):
        self.target_pid = target_pid
        self.executable_path = executable_path
        self.running = True

    def monitor(self):
        logger.info(f"Watchdog started, monitoring PID: {self.target_pid}")
        while self.running:
            try:
                # Check if process exists
                if not psutil.pid_exists(self.target_pid):
                    logger.warning(f"Target PID {self.target_pid} died! Respawning...")
                    self._respawn()
                    break # End this watchdog, the new process will spawn its own
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
            time.sleep(0.5)

    def _respawn(self):
        try:
            # Re-launch the application
            subprocess.Popen([sys.executable, self.executable_path])
            logger.info("Successfully respawned application.")
        except Exception as e:
            logger.error(f"Failed to respawn: {e}")

def run_watchdog(target_pid: int, executable_path: str):
    watchdog = AntiKillWatchdog(target_pid, executable_path)
    watchdog.monitor()

def ensure_dual_process():
    """
    Call this at the very beginning of the main application.
    It will start a detached watchdog process.
    """
    if os.name != 'nt':
        return

    current_pid = os.getpid()
    executable_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
    
    logger.info("Starting Watchdog Process...")
    # Using multiprocessing.Process to start an independent watchdog
    p = Process(target=run_watchdog, args=(current_pid, executable_path), daemon=True)
    p.start()
