import asyncio
import sys
import os

# Ensure the current directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from core.state import global_state

print("Client States:", global_state.get_clients())
