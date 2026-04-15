from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

from app.blob_storage import sync_rag_documents, log_visitor_to_blob, save_findings_to_blob, load_findings_from_blob
from app.rag import init_chroma
from app.agent import process_chat, run_autonomous_check

# This allows the scheduler to "kill" an old stuck job if a new toggle comes in
scheduler = BackgroundScheduler(job_defaults={'max_instances': 2})

def _agent_cycle():
    print(f"[{datetime.utcnow().isoformat()}] Running autonomous agent cycle...")
    new_findings = run_autonomous_check()
    for f in new_findings: 
        f["timestamp"] = datetime.utcnow().isoformat()
    
    all_findings = load_findings_from_blob()
    all_findings.extend(new_findings)
    save_findings_to_blob(all_findings)
    print(f"Agent finished. Total findings stored: {len(all_findings)}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up... Syncing RAG docs from Azure Blob.")
    sync_rag_documents()
    init_chroma()
    
    scheduler.add_job(_agent_cycle, "interval", minutes=5, id="agent_check")
    scheduler.pause_job("agent_check") # <--- NEW: Pauses the agent on startup
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="Building 59 AI Backend", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- NEW: AGENT CONTROL ENDPOINTS ---
@app.get("/agent/status")
async def get_agent_status():
    """Returns whether the autonomous agent is currently running."""
    job = scheduler.get_job("agent_check")
    is_enabled = job is not None and job.next_run_time is not None
    return {"enabled": is_enabled}

@app.post("/agent/toggle")
async def toggle_agent():
    """Pauses or resumes the agent. If resuming, forces an immediate run."""
    job = scheduler.get_job("agent_check")
    if not job:
        return {"enabled": False}

    if job.next_run_time is not None:
        scheduler.pause_job("agent_check")
        print("Autonomous Agent PAUSED via UI.")
        return {"enabled": False}
    else:
        scheduler.resume_job("agent_check")
        # Modify the next run time to right NOW so it runs immediately
        scheduler.modify_job("agent_check", next_run_time=datetime.now())
        print("Autonomous Agent RESUMED and triggered immediately via UI.")
        return {"enabled": True}
# ------------------------------------

class VisitorRequest(BaseModel):
    name: str
    email: str

@app.post("/visitor")
async def log_visitor(req: VisitorRequest):
    visitor_data = {"timestamp": datetime.utcnow().isoformat(), "name": req.name, "email": req.email}
    log_visitor_to_blob(visitor_data) # Saves safely to Azure Blob
    return {"status": "ok"}

@app.get("/admin/visitors")
async def get_visitors():
    """Unprotected endpoint as requested."""
    return {"message": "Visitor tracking is active and logging directly to Azure Blob Storage."}

@app.get("/findings")
async def get_findings(limit: int = 20):
    findings = load_findings_from_blob()
    return findings[-limit:]

@app.websocket("/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    history = []
    try:
        while True:
            user_msg = await ws.receive_text()
            
            # Wrap the AI call in a safety net
            try:
                response = await process_chat(user_msg, history)
                history.append({"role": "user", "content": user_msg})
                history.append({"role": "assistant", "content": response})
                history = history[-10:] # Keep last 10 messages for context
                await ws.send_text(response)
            except Exception as ai_error:
                error_msg = f"Sorry, the AI encountered a backend error: {str(ai_error)}"
                print(f"Chat Exception: {ai_error}")
                await ws.send_text(error_msg)
                
    except WebSocketDisconnect:
        print("WebSocket disconnected")