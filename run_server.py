import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from server.main_pro import EnterpriseSystem

if __name__ == "__main__":
    system = EnterpriseSystem()
    system.start()
