"""ASGI smoke tests for the browser backend."""

import asyncio
import json
import unittest

from httpx import ASGITransport, AsyncClient

from card_duel.web.app import create_app


class WebAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_root_explains_backend_status(self):
        transport = ASGITransport(app=create_app())
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/")
            favicon = await client.get("/favicon.ico")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Card Duel Web API", response.text)
        self.assertIn("浏览器前端在独立的", response.text)
        self.assertIn("原子弃牌", response.text)
        self.assertEqual(favicon.status_code, 204)

    async def test_health_endpoint(self):
        transport = ASGITransport(app=create_app())
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "protocol_version": 2, "rooms": 0},
        )

    async def test_websocket_can_create_room(self):
        app = create_app()
        incoming = asyncio.Queue()
        outgoing = []
        await incoming.put({"type": "websocket.connect"})
        await incoming.put(
            {
                "type": "websocket.receive",
                "text": json.dumps({"action": "create_room", "data": {}}),
            }
        )
        await incoming.put({"type": "websocket.disconnect", "code": 1000})

        async def receive():
            return await incoming.get()

        async def send(message):
            outgoing.append(message)

        await app(
            {
                "type": "websocket",
                "asgi": {"version": "3.0", "spec_version": "2.4"},
                "scheme": "ws",
                "path": "/ws",
                "raw_path": b"/ws",
                "query_string": b"",
                "root_path": "",
                "headers": [],
                "client": ("127.0.0.1", 50000),
                "server": ("testserver", 80),
                "subprotocols": [],
                "state": {},
            },
            receive,
            send,
        )

        sent_payloads = [
            json.loads(message["text"])
            for message in outgoing
            if message["type"] == "websocket.send"
        ]
        self.assertEqual(outgoing[0]["type"], "websocket.accept")
        self.assertEqual(
            [payload["type"] for payload in sent_payloads],
            ["connected", "room_created", "room_state"],
        )
        self.assertEqual(len(sent_payloads[1]["data"]["room_code"]), 6)


if __name__ == "__main__":
    unittest.main()
