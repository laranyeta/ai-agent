from fastapi import FastAPI
from pydantic import BaseModel
from agent import response

app = FastAPI(
    title="Job Hunting AI Agent",
    description="AI agent for job hunting that analyzes job postings and my CV, built with the Claude API, RAG and MPC.",
)

class Query(BaseModel):
    text: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ask")
def ask(question: Query):
    reply = response(question.text)
    return {"question": question.text, "response": reply}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
