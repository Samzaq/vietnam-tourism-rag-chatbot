from typing import List
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from chat import chatbot
import json
import time
import asyncio

app = FastAPI()

# Allow frontend (e.g. Next.js) to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # your Next.js dev URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Input data models
class Message(BaseModel):
    role: str
    content: str

class RequestData(BaseModel):
    messages: List[Message]
    language: str


@app.post("/process")
async def process_messages(request_data: RequestData):
    messages = [{"role": msg.role, "content": msg.content} for msg in request_data.messages]
    language = request_data.language

    async def event_stream():
        try:
            buffer = ""
            for chunk in chatbot(messages, language):
                if not chunk:
                    continue

                buffer += chunk

                # Gửi khi buffer đủ dài hoặc có dấu kết thúc câu
                if len(buffer) > 100 or chunk.endswith((".", "!", "?", "\n")):
                    yield f"data: {json.dumps({'content': buffer})}\n\n"
                    buffer = ""
                    await asyncio.sleep(0.05)

            # Gửi phần còn lại
            if buffer:
                yield f"data: {json.dumps({'content': buffer})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
