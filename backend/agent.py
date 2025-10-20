import asyncio 
import aiohttp
import os
from dotenv import load_dotenv 

from langchain_core.callbacks.base import AsyncCallbackHandler
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import ConfigurableField
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr

load_dotenv()

# APi Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT")
LANGCHAIN_ENDPOINT = os.getenv("LANGCHAIN_ENDPOINT")

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

# LLM With Configurable Fields for Streaming
llm = ChatOpenAI(
    api_key=OPENAI_API_KEY, 
    model="gpt-4o-mini", 
    temperature=0.0).configurable_fields(
        callbacks=ConfigurableField(
            id="callbacks",
            name="callbacks",
            description="A List of Callbacks to use for the LLM`s"
        )
)

# Prompt for the LLM
prompt = ChatPromptTemplate.from_messages([
    ("system",(
        "You're a helpful assistant. When answering a user's question "
        "you should first use one of the tools provided. After using a "
        "tool the tool output will be provided back to you. When you have "
        "all the information you need, you MUST use the final_answer tool "
        "to provide a final answer to the user. Use tools to answer the "
        "user's CURRENT question, not previous questions."
    )),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

class Article(BaseModel):
    title: str
    source: str
    link: str
    snippet: str

    @classmethod
    def from_serpapi_result(cls, result: dict) -> "Article":
        return cls(
            title=result["title"],
            source=result["source"],
            link=result["link"],
            snippet=result["snippet"],
        )

# Tool for the LLM to use, Includes a description that allows them to read what the Tool Does
@tool
async def add(x: float, y: float) -> float:
    """Add 'x' and 'y'."""
    return x + y

@tool
async def multiply(x: float, y: float) -> float:
    """Multiply 'x' and 'y'."""
    return x * y

@tool
async def exponentiate(x: float, y: float) -> float:
    """Raise 'x' to the power of 'y'."""
    return x ** y

@tool
async def subtract(x: float, y: float) -> float:
    """Subtract 'x' from 'y'."""
    return y - x

@tool
async def final_answer(answer: str, tools_used: list[str]) -> dict[str, str | list[str]]:
    """Use this tool to provide a final answer to the user."""
    return {"answer": answer, "tools_used": tools_used}

@tool
async def serpapi(query: str) -> list[Article]:
    """Use this tool to search the web."""
    params = {
        "api_key": SERPAPI_API_KEY,
        "engine": "google",
        "q": query,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://serpapi.com/search",
            params=params
        ) as response:
            results = await response.json()
    return [Article.from_serpapi_result(result) for result in results["organic_results"]]

# All Tools and the map from tool name to the coroutine for python to execute the async function
tools = [add, multiply, exponentiate, subtract, final_answer, serpapi]
name2tool = {tool.name: tool.coroutine for tool in tools}

# Queue class to emable streaming
class QueueCallbackHandler(AsyncCallbackHandler):
    
    # Intiaise the queue and of the final answer has been seen in constructor
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        # if we see the final answer then we set this to true to state that we are done
        self.final_answer_seen = False
    
    # this iterates when the queue recieves a token, if it is empty async wait else then stay at the token 
    # Makes it an asynchronous iterator, and when queue is empty it is NON BLOCKING, if token is Done then it stops the iterator else it sends it out to the loop that is consuming the stream
    async def __aiter__(self):
        while True:
            if self.queue.empty():
                await asyncio.sleep(0.1)
            else:
                item = await self.queue.get()
                if item == "<<DONE>>":
                    return
                else : 
                    yield item
    
    # Function on every new token
    async def on_llm_new_token(self, *args, **kwargs) -> None:
        """Puts a New Token into the Queue"""
        
        chunk = kwargs.get("chunk")
        if chunk :
        # Check for final_answer tool call
            tool_calls = getattr(chunk.message, "tool_call_chunks")
            if tool_calls :
                # If it is the final answer set the Boolean var to True
                if tool_calls[0]["name"] == "final_answer" :
                    self.final_answer_seen = True

        # Adds an item ot the queue immediately and is Non Blocking, if Queue is full it raises and exception
        # We have an unbounded queue size so this wont block the queue
        self.queue.put_nowait(kwargs.get("chunk"))
        return

    # When LLM Ends
    async def on_llm_end(self, *args, **kwargs) -> None:
        if self.final_answer_seen:
            self.queue.put_nowait("<<DONE>>")
        else:
            self.queue.put_nowait("<<STEP_END>>")

# From tool message it grabs the Name and arguements, uses the map to execute it and returns a Langchain Tool Message
async def execute_tool(tool_call: AIMessage) -> ToolMessage:
    """Execute a Tool Call"""
    tool_name = tool_call.tool_calls[0]["name"]
    tool_args = tool_call.tool_calls[0]["args"]
    tool_call_id = tool_call.tool_call_id
    tool_out = await name2tool[tool_name](**tool_args)
    tool_exec = ToolMessage(content=f"{tool_out}", tool_call_id=tool_call_id)
    return tool_exec

# Custome Agent
class CustomAgentExecutor:
    """A Custom Agent Executor that uses a Queue Callback Handler"""
    
    # Constructor initialises Agent, Chat history and Agent scratchpad
    def __init__(self, max_iterations : int = 3):
        self.chat_history : list[BaseMessage] = []
        self.max_iterations = max_iterations
        self.agent = (
            {
                "input" : lambda x : x["input"],
                "chat_history" : lambda x : x["chat_history"],
                "agent_scratchpad" : lambda x : x.get("agent_scratchpad", [])
            }
            |prompt
            |llm.bind_tools(tools, tool_choice="any")
        )
    
    # When the Agent makes a Call, Invokes the LLM
    async def invoke(self, input: str, streamer : QueueCallbackHandler) -> dict :
        
        # Intialise the Variables
        count = 0
        final_answer : str | None = None
        agent_scratchpad : list[AIMessage | ToolMessage] = []
        tools_used : list[str] = []

        # Function to handle the Stream
        async def stream(query: str) -> list[AIMessage] :
            # Add Streamer Callback as Config to the LLM
            response = self.agent.with_config(
                callbacks = [streamer]
            )

            outputs = []

            # We iterate through the streaming tokens
            async for token in response.astream({
                "input" : query,
                "chat_history" : self.chat_history,
                "agent_scratchpad" : agent_scratchpad
            }) :
                
                # Get any Tool Calls, if first add it to outputs else and it to the last index in outputs, builds up a sentance
                tool_calls = getattr(token, "tool_call_chunks")
                if tool_calls :

                    if tool_calls[0]["id"] :
                        outputs.append(token)
                    else : 
                        outputs[-1] += token
                else :
                    pass
            # Return an AI Message with the content, tool calls and the tool call id
            return [
                AIMessage(
                    content =  x.content,
                    tool_calls=x.tool_calls,
                    tool_call_id=x.tool_calls[0]["id"]
                )
                for x in outputs
            ]
        
        # Iterate 3 times or until the final answer is found
        while count < self.max_iterations :

            # Get tool calls and execute all the tools 
            tool_calls = await stream(input)
            tool_obs = await asyncio.gather(
                *[execute_tool(tool_call) for tool_call in tool_calls]
            )
            # Map the tool call id to the tool observation
            id2tool_obs = {tool_call.tool_call_id: tool_obs for tool_call, tool_obs in zip(tool_calls, tool_obs)}
            # Extend the agent scratchpad with the tool call and the tool observation
            for tool_call in tool_calls :
                agent_scratchpad.extend([tool_call, id2tool_obs[tool_call.tool_call_id]])
            
            count += 1

            # Check if the final answer is found
            found_final_answer = False
            for tool_call in tool_calls :
                if tool_call.tool_calls[0]["name"] == "final_answer" :
                    found_final_answer = True 
                    final_answer = tool_call.tool_calls[0]["args"]["answer"]
                    break
            # If the final answer is found break the loop
            if found_final_answer :
                break
        # Add the human message and the final answer to the chat history
        self.chat_history.extend(
            [
                HumanMessage(content=input),
                AIMessage(content=final_answer if final_answer else "No final answer found")
            ]
        )
        
        return {"answer" : final_answer, "tools_used" : tools_used}
        
agent_executor = CustomAgentExecutor()