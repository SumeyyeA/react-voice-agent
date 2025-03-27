import uvicorn
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from langchain_openai_voice import OpenAIVoiceReactAgent
from server.utils import websocket_stream
from server.prompt import INSTRUCTIONS
from server.tools import TOOLS

from server.save_recording import save_recording

brand_name = "Tesla"

async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
  
    instructions = INSTRUCTIONS.replace("{MARKA_ADI}", brand_name)

    browser_receive_stream = websocket_stream(websocket)
    
    agent = OpenAIVoiceReactAgent(
        model="gpt-4o-realtime-preview",
        tools=TOOLS,
        instructions=instructions,
        temperature=0.1,  
    )

    await agent.aconnect(browser_receive_stream, websocket.send_text)

async def homepage(request):
    with open("src/server/static/index.html") as f:
        html = f.read()
    return HTMLResponse(html)


routes = [
    Route("/", homepage),
    WebSocketRoute("/ws", websocket_endpoint),
    Route("/save_recording", save_recording, methods=["POST"]),
]

app = Starlette(debug=True, routes=routes)
app.mount("/", StaticFiles(directory="src/server/static"), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
