from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel

from .main import run_agent
import asyncio

app = FastAPI()

from pathlib import Path

BASE_DIR = Path(__file__).parent
from pathlib import Path

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)

class ChatRequest(BaseModel):
    query: str

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>KYC Agentic AI Demo</title>

<style>

body{
    font-family: Arial;
    width: 1000px;
    margin:auto;
    margin-top:20px;
}

#chat{
    border:1px solid #ddd;
    height:500px;
    overflow-y:auto;
    padding:15px;
}

textarea{
    width:100%;
    height:100px;
}

button{
    margin-top:10px;
    padding:10px;
}

.user{
    color:blue;
}

.agent{
    color:green;
}

</style>

</head>

<body>

<h2>🔐 PBAC Agentic AI KYC Demo</h2>

<div id="chat"></div>

<br>

<textarea id="prompt">
Summarize ABC Corp KYC profile
</textarea>

<br>

<button onclick="sendQuery()">
Send
</button>

<script>

async function sendQuery(){

    const prompt =
        document.getElementById("prompt").value;

    let response =
        await fetch(
            "/chat",
            {
                method:"POST",

                headers:{
                    "Content-Type":
                    "application/json"
                },

                body:JSON.stringify({
                    query:prompt
                })
            }
        );

    let data =
        await response.json();

    let chat =
        document.getElementById("chat");

    chat.innerHTML +=
        "<p class='user'><b>User:</b> "
        + prompt +
        "</p>";

    chat.innerHTML +=
        "<p class='agent'><b>Assistant:</b><br>"
        + data.response +
        "</p><hr>";

    chat.scrollTop =
        chat.scrollHeight;
}

</script>
<button onclick="fillPrompt('What is Customer Due Diligence?')">
CDD
</button>

<button onclick="fillPrompt('Get customer risk profile for ABC Corp')">
Risk Profile
</button>

<button onclick="fillPrompt('Summarize ABC Corp KYC profile')">
KYC Summary
</button>

<button onclick="fillPrompt('Show beneficial owner national ID')">
Sensitive Data
</button>
</body>
</html>
"""


@app.post("/chat")
async def chat(req: ChatRequest):

    result = await asyncio.to_thread(
        run_agent,
        req.query
    )

    return {
        "response": result
    }