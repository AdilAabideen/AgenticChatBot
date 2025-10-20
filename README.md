# Agentic ChatBot

This project is a full-stack, streaming-first agentic chatbot. It features a React/TypeScript frontend and a Python/FastAPI backend that leverages LangChain and OpenAI to provide thoughtful, tool-assisted answers to user queries. The application visualizes the agent's step-by-step reasoning process in real-time as it works towards a final answer.

## How It Works

The application is composed of a frontend and a backend that communicate via a streaming API endpoint.

### Backend

The backend is built with Python using FastAPI and LangChain.

-   **`main.py`**: A FastAPI server that exposes a single endpoint, `/chat`. This endpoint accepts a user's question, initiates the agent process, and streams the agent's thoughts and final answer back to the client.
-   **`agent.py`**: This file contains the core logic for the agent.
    -   **LLM**: It uses `gpt-4o-mini` via `ChatOpenAI` from the `langchain-openai` library.
    -   **Tools**: The agent is equipped with several tools:
        -   `add`, `subtract`, `multiply`, `exponentiate` for mathematical calculations.
        -   `serpapi` for performing web searches to answer questions that require up-to-date information.
        -   `final_answer` is a special tool the agent MUST use to deliver its conclusive response to the user.
    -   **Custom Agent Executor**: A custom `CustomAgentExecutor` class manages the agent's lifecycle. It invokes the agent, executes the tools it decides to use, and feeds the results back into the agent until a `final_answer` is generated or the maximum number of iterations is reached.
    -   **Streaming**: A `QueueCallbackHandler` is implemented to enable real-time streaming. As the LLM generates tokens for its thought process (i.e., which tool to use and with what arguments), these tokens are put into an `asyncio.Queue`. The FastAPI response streams these tokens wrapped in custom tags (`<step>`, `<step_name>`) to the frontend, allowing for a live view of the agent's "thinking" process.

### Frontend

The frontend is a modern React application built with TypeScript and Vite.

-   **`App.tsx`**: The root component that manages the overall state of the chat, including the list of questions and answers.
-   **`TextArea.tsx`**: This component provides the user input field. When a message is submitted:
    -   It makes a `POST` request to the backend's `/chat` endpoint.
    -   It reads the streaming response chunk by chunk.
    -   It parses the custom tags (`<step>`, `<step_name>`) and the JSON payloads to reconstruct the agent's reasoning steps in real-time.
    -   The `incomplete-json-parser` library is used to safely handle JSON objects that may be split across multiple stream chunks.
-   **`Output.tsx`**: This component is responsible for rendering the conversation. For each user query, it displays:
    -   The original question.
    -   A collapsible "Steps" section that shows each tool the agent used and the arguments it provided. A pulsing green dot indicates that the agent is currently working.
    -   The final answer, rendered from Markdown.
    -   A list of tools used to generate the answer.
-   **`MarkdownRenderer.tsx`**: A component that uses `react-markdown` and `remark-gfm` to render the final answer, supporting GitHub Flavored Markdown.

## Features

-   **Agentic Architecture**: The backend agent can reason and decide which tools to use to answer a query.
-   **Tool Integration**: Includes tools for real-time web searches (SerpApi) and mathematical calculations.
-   **Real-time Streaming**: The agent's entire thought process, from selecting a tool to generating the final response, is streamed to the user interface.
-   **Step-by-Step Visualization**: The UI clearly displays each step the agent takes, providing transparency into its reasoning.
-   **Full-Stack Application**: A complete, self-contained project with a React frontend and a FastAPI backend.
-   **Markdown Support**: Final answers are rendered as Markdown, allowing for rich formatting like lists, links, and tables.

## Setup and Installation

### Prerequisites

-   Python 3.8+
-   Node.js and npm

### Backend Setup

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: A `requirements.txt` file is not included. You can install the necessary packages manually based on the imports in `agent.py` and `main.py`):*
     ```bash
    pip install "fastapi[all]" "uvicorn[standard]" langchain langchain-openai python-dotenv aiohttp
    ```

4.  **Create an environment file:**
    Create a `.env` file in the `backend` directory.

5.  **Add API Keys:**
    Add your API keys to the `.env` file. You will need an OpenAI key and a SerpApi key. LangSmith keys are optional for tracing.
    ```env
    OPENAI_API_KEY="sk-..."
    SERPAPI_API_KEY="..."

    # Optional for LangSmith Tracing
    LANGCHAIN_API_KEY="..."
    LANGCHAIN_TRACING_V2="true"
    LANGCHAIN_PROJECT="Your-Project-Name"
    LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
    ```

6.  **Run the backend server:**
    ```bash
    uvicorn main:app --reload
    ```
    The server will be running on `http://localhost:8000`.

### Frontend Setup

1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend
    ```

2.  **Install Node.js dependencies:**
    ```bash
    npm install
    ```

3.  **Run the development server:**
    ```bash
    npm run dev
    ```
    The frontend will be available at `http://localhost:5173`.

## Usage

1.  Ensure both the backend and frontend servers are running.
2.  Open your browser and navigate to `http://localhost:5173`.
3.  Type a question into the text area. You can ask something that requires a web search, like "What is the weather in London?", or a calculation, like "What is 25 to the power of 3?".
4.  Press Enter or click the send button.
5.  Watch as the agent's steps appear in the UI, followed by the final answer. You can expand or collapse the "Steps" section to see the details of the agent's reasoning.
