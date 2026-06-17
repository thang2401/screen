from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import asyncio
from datetime import datetime
from server.api.auth import get_current_admin
from core.state import global_state

router = APIRouter(prefix="/api/v1")

# Queue to pass commands to the WebSocket server
command_queue = asyncio.Queue()

class ClientStatus(BaseModel):
    client_id: str
    is_online: bool
    fps: float
    cpu_usage: Optional[float] = None
    last_seen: str

class ControlCommand(BaseModel):
    client_id: str
    command: str 
    args: Optional[dict] = None

@router.get("/clients", response_model=List[ClientStatus])
async def get_clients(admin: str = Depends(get_current_admin)):
    """Get real-time status of all clients from Global Memory Data Bus"""
    clients = []
    for cid, state in global_state.get_clients().items():
        clients.append(ClientStatus(
            client_id=cid,
            is_online=state.get("is_online", False),
            fps=state.get("fps", 0.0),
            last_seen=state.get("last_seen", datetime.utcnow().isoformat())
        ))
    return clients

@router.post("/control")
async def send_control_command(cmd: ControlCommand, admin: str = Depends(get_current_admin)):
    """Send command to a specific client"""
    if cmd.client_id not in global_state.client_states and cmd.client_id != "all":
        raise HTTPException(status_code=404, detail="Client not found")
        
    await command_queue.put(cmd.dict())
    
    return {"status": "success", "message": f"Command {cmd.command} queued for {cmd.client_id}"}
