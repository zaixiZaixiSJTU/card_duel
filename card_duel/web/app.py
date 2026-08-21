"""FastAPI entry point for the Card Duel browser backend."""

from __future__ import annotations

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from card_duel.web.protocol import WEB_PROTOCOL_VERSION
from card_duel.web.rooms import RoomManager


def create_app(manager: RoomManager | None = None) -> FastAPI:
    room_manager = manager or RoomManager()
    app = FastAPI(title="Card Duel Web API", version="0.1.0")
    app.state.room_manager = room_manager

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Card Duel Web API</title>
  <style>
    :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
    body { max-width: 720px; margin: 12vh auto; padding: 0 24px; line-height: 1.7; }
    code { padding: .15rem .35rem; border-radius: 4px; background: #8882; }
    a { color: #4f8cff; }
  </style>
</head>
<body>
  <h1>Card Duel Web API</h1>
  <p>权威房间服务正在运行，Web 协议版本为 <strong>2</strong>。</p>
  <p>当前阶段提供房间、权威五阶段回合、出牌、弃牌和选择恢复；游戏 Web 前端尚未接入。</p>
  <ul>
    <li><a href="/health">健康检查</a></li>
    <li><a href="/docs">API 文档</a></li>
    <li>WebSocket：<code>/ws</code></li>
  </ul>
</body>
</html>"""

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "protocol_version": WEB_PROTOCOL_VERSION,
            "rooms": len(room_manager.rooms),
        }

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        client_id = await room_manager.connect(websocket)
        try:
            while True:
                payload = await websocket.receive_json()
                await room_manager.handle(client_id, payload)
        except WebSocketDisconnect:
            pass
        finally:
            await room_manager.disconnect(client_id)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("card_duel.web.app:app", host="0.0.0.0", port=8000)
