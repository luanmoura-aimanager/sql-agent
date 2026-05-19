from agent import run_agent
from fastapi import FastAPI
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

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    history = [{"role": m.role, "content": m.content} for m in request.history]
    answer = run_agent(request.question, history)
    return QueryResponse(answer=answer)
