from agent import run_agent
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI()

class Message(BaseModel):
    role: str      # "user" ou "assistant"
    content: str

class QueryRequest(BaseModel):
    question: str
    history: List[Message] = []   # opcional — default é lista vazia

class QueryResponse(BaseModel):
    answer: str

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    try:
        history = [{"role": m.role, "content": m.content} for m in request.history]
        answer = run_agent(request.question, history)
        return QueryResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
