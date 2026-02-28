from __future__ import annotations

import json
from typing import Any, Dict, Set

from aiohttp import web, WSMsgType


class RealTimePush:
    """简单的实时推送管理器，支持广播与心跳"""

    def __init__(self):
        self.connections: Set[web.WebSocketResponse] = set()

    async def handle(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=15)
        await ws.prepare(request)
        self.connections.add(ws)

        await ws.send_json({"type": "welcome", "message": "connected", "ts": request.loop.time()})

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                # 回音/心跳
                if msg.data == 'ping':
                    await ws.send_str('pong')
                else:
                    await ws.send_json({"type": "ack", "echo": msg.data})
            elif msg.type == WSMsgType.ERROR:
                break

        self.connections.discard(ws)
        return ws

    async def broadcast(self, event_type: str, payload: Dict[str, Any]):
        if not self.connections:
            return
        message = json.dumps({"type": event_type, "data": payload})
        dead = []
        for ws in self.connections:
            try:
                await ws.send_str(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.connections.discard(ws)
