import asyncio

from agent import QueueCallbackHandler, agent_executor
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Add CORS Middleware to allow all origins, credentials, methods and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def token_generator(content : str, streamer : QueueCallbackHandler) : 
    # Create a task to invoke the agent executor, using asyncio
    task = asyncio.create_task(agent_executor.invoke(
        input=content,
        streamer=streamer
    ))

    # Iterate through the streamer and yield the tokens
    async for token in streamer : 
        try :
            # If the token is the step end then yield the step end
            if token == "<<STEP_END>>" :
                yield "</step>"
            elif tool_calls := getattr(token.message, "tool_call_chunks") :
                # If the tool calls are present then yield the tool name
                if tool_name := tool_calls[0]["name"]:
                    yield f"<step><step_name>{tool_name}</step_name>"
                # If the tool calls are present then yield the tool arguments
                if tool_calls[0]["args"] :
                    yield tool_calls[0]["args"]
        except Exception as e :
            # If an error is encountered then yield the error
            yield f"<error>{e}</error>"
            continue
    
    # Wait for the task to complete
    await task

@app.post("/chat")
async def chat(content: str) :
    # Create a queue to store the tokens
    queue : asyncio.Queue = asyncio.Queue()
    # Create a streamer to handle the tokens
    streamer = QueueCallbackHandler(queue)
    return StreamingResponse(
        token_generator(content, streamer),
        media_type="text/event-stream",
        headers={
            "Cache-Control" : "no-cache",
            "Connection" : "keep-alive",
        }
    )
