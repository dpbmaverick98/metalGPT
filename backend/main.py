"""
MetalGPT Backend - FastAPI + WebSocket server
"""
import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from casting.geometry import GeometryProcessor
from casting.simulation import FDMSimulator
from casting.optimizer import CastingOptimizer
from casting.improvement_loop import AIImprovementLoop
from chat.handler import ChatHandler

app = FastAPI(title="MetalGPT API", version="0.1.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Storage
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Active sessions
sessions: Dict[str, dict] = {}

# Initialize components
geometry_processor = GeometryProcessor()
simulator = FDMSimulator()
optimizer = CastingOptimizer()
chat_handler = ChatHandler()


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload STEP/STL file and process geometry"""
    session_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{session_id}_{file.filename}"
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Process geometry
    try:
        geometry_data = geometry_processor.process(str(file_path))
        sessions[session_id] = {
            "file_path": str(file_path),
            "geometry": geometry_data,
            "risers": [],
            "gating": None,
            "simulation_results": None
        }
        
        return {
            "success": True,
            "session_id": session_id,
            "geometry": geometry_data,
            "message": f"Loaded {file.filename}. Found {len(geometry_data.get('hotspots', []))} hot spots."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/chat")
async def chat_endpoint(msg: ChatMessage):
    """HTTP chat endpoint"""
    session_data = sessions.get(msg.session_id, {}) if msg.session_id else {}
    
    response = await chat_handler.process_message(
        message=msg.message,
        session_data=session_data
    )
    
    # Update session if modified
    if msg.session_id and msg.session_id in sessions:
        sessions[msg.session_id].update(response.get("session_updates", {}))
    
    return response


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket for real-time chat"""
    await websocket.accept()
    session_id = None
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle session management
            if "session_id" in message:
                session_id = message["session_id"]
            
            session_data = sessions.get(session_id, {}) if session_id else {}
            
            # Process message
            response = await chat_handler.process_message(
                message=message.get("text", ""),
                session_data=session_data,
                websocket=websocket
            )
            
            # Send response
            await websocket.send_json({
                "type": "response",
                "text": response.get("text", ""),
                "data": response.get("data", {}),
                "actions": response.get("actions", [])
            })
            
            # Update session
            if session_id and session_id in sessions:
                sessions[session_id].update(response.get("session_updates", {}))
                
    except WebSocketDisconnect:
        print(f"Client disconnected: {session_id}")


@app.post("/api/analyze")
async def analyze_geometry(session_id: str):
    """Run geometric analysis on loaded model"""
    if session_id not in sessions:
        return {"error": "Session not found"}
    
    session = sessions[session_id]
    geometry = session["geometry"]
    
    # Run analysis
    analysis = geometry_processor.analyze(geometry)
    
    return {
        "hotspots": analysis["hotspots"],
        "modulus_field": analysis["modulus_field"],
        "feeding_zones": analysis["feeding_zones"],
        "recommendations": analysis["recommendations"]
    }


@app.post("/api/optimize")
async def optimize_design(session_id: str, material: str = "aluminum_a356"):
    """Run AI optimization for casting design"""
    if session_id not in sessions:
        return {"error": "Session not found"}
    
    session = sessions[session_id]
    
    # Run optimizer
    result = optimizer.optimize(
        geometry=session["geometry"],
        material=material,
        progress_callback=lambda p: asyncio.create_task(
            send_progress(session_id, p)
        ) if session_id in ws_connections else None
    )
    
    session["risers"] = result["risers"]
    session["gating"] = result["gating"]
    
    return {
        "success": True,
        "risers": result["risers"],
        "gating": result["gating"],
        "yield": result["yield"],
        "message": f"Optimization complete. Yield: {result['yield']:.1f}%"
    }


@app.post("/api/simulate")
async def run_simulation(session_id: str):
    """Run FDM solidification simulation"""
    if session_id not in sessions:
        return {"error": "Session not found"}
    
    session = sessions[session_id]
    
    # Run simulation
    results = simulator.run(
        geometry=session["geometry"],
        risers=session.get("risers", []),
        gating=session.get("gating"),
        material=session.get("material", "aluminum_a356")
    )
    
    session["simulation_results"] = results
    
    return {
        "success": True,
        "defects": results["defects"],
        "solidification_time": results["solidification_time"],
        "porosity_map": results["porosity_map"],
        "message": f"Simulation complete. Defects: {len(results['defects'])}"
    }


@app.post("/api/improve")
async def run_improvement_loop(
    session_id: str,
    material: str = "aluminum_a356",
    max_iterations: int = 10,
    websocket: WebSocket = None
):
    """
    Run AI improvement loop - automatically optimize until defects eliminated
    """
    if session_id not in sessions:
        return {"error": "Session not found"}
    
    session = sessions[session_id]
    
    # Initialize improvement loop
    improvement_loop = AIImprovementLoop(max_iterations=max_iterations)
    
    # Progress callback
    async def progress_callback(progress: dict):
        progress["session_id"] = session_id
        await send_progress(session_id, progress)
    
    # Get AI client if available
    ai_client = None
    if hasattr(chat_handler, 'anthropic_client'):
        ai_client = chat_handler.anthropic_client
    elif hasattr(chat_handler, 'openai_client'):
        ai_client = chat_handler.openai_client
    
    # Run improvement loop
    result = await improvement_loop.run_improvement_loop(
        geometry=session["geometry"],
        material=material,
        simulator=simulator,
        optimizer=optimizer,
        ai_client=ai_client,
        progress_callback=progress_callback
    )
    
    # Update session with final design
    session["risers"] = result["final_design"]["risers"]
    session["gating"] = result["final_design"]["gating"]
    session["simulation_results"] = result["final_simulation"]
    session["improvement_history"] = result["iteration_history"]
    
    return {
        "success": True,
        "converged": result["converged"],
        "iterations": result["iteration_count"],
        "final_defects": len(result["final_defects"]),
        "final_yield": result["final_design"]["yield"],
        "risers": result["final_design"]["risers"],
        "gating": result["final_design"]["gating"],
        "iteration_history": result["iteration_history"],
        "summary": result["summary"],
        "message": f"Improvement complete after {result['iteration_count']} iterations. "
                   f"{'✅ Defect-free!' if result['converged'] else '⚠️ ' + str(len(result['final_defects'])) + ' defects remain'}"
    }


# WebSocket connections for progress updates
ws_connections: Dict[str, WebSocket] = {}

async def send_progress(session_id: str, progress: dict):
    """Send progress update to connected client"""
    if session_id in ws_connections:
        await ws_connections[session_id].send_json({
            "type": "progress",
            "data": progress
        })


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
