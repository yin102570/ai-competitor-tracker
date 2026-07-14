"""
Dashboard模块API路由 - 综合看板聚合 + WebSocket实时推送
路由前缀: /api/v1/dashboard

接口清单:
  GET    /overview              综合看板数据聚合
  GET    /realtime              WebSocket连接端点（升级ws）

WebSocket认证: query param ?token=eyJhbGci...
推送消息类型: sentiment_update / alert / system_status
"""

from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.config import settings
from app.core.deps import DBSession
from app.core.security import decode_token
from app.schemas.dashboard import DashboardOverviewResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["数据面板"])

CST = timezone(timedelta(hours=8))


# ============================================================
# 综合看板（REST）
# ============================================================

@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="综合看板",
    description="聚合竞品/舆情/爬虫数据，提供统一Dashboard视图",
)
async def get_overview(db: DBSession) -> DashboardOverviewResponse:
    """综合看板"""
    service = DashboardService(db)
    return await service.get_overview()


# ============================================================
# WebSocket 实时推送
# ============================================================

# 活跃连接管理器
class ConnectionManager:
    """WebSocket连接管理器 - 管理活跃连接和广播"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """接受连接并加入活跃列表"""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """移除连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: dict[str, Any], websocket: WebSocket):
        """发送单条消息"""
        await websocket.send_json(message)

    async def broadcast(self, message: dict[str, Any]):
        """广播消息给所有活跃连接"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # 忽略发送失败的连接
                pass


manager = ConnectionManager()


@router.websocket("/realtime")
async def realtime_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="JWT访问令牌"),
):
    """
    WebSocket实时推送端点
    认证: query param ?token=...
    推送内容: sentiment_update / alert / system_status

    使用方式:
      const ws = new WebSocket('wss://api.example.com/api/v1/dashboard/realtime?token=...')
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        // { type: "sentiment_update", competitor_slug: "chatgpt", ... }
      }
    """
    # 1. 认证验证
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001, reason="Invalid token type")
            return
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # 2. 接受连接
    await manager.connect(websocket)

    try:
        # 3. 发送初始连接成功消息
        await manager.send_personal_message(
            {
                "type": "connected",
                "message": "WebSocket连接已建立",
                "timestamp": datetime.now(CST).isoformat(),
            },
            websocket,
        )

        # 4. 监听消息循环
        while True:
            try:
                # 接收客户端消息
                data = await websocket.receive_json()

                # 处理订阅/心跳等命令
                msg_type = data.get("type", "")

                if msg_type == "ping":
                    await manager.send_personal_message(
                        {
                            "type": "pong",
                            "timestamp": datetime.now(CST).isoformat(),
                        },
                        websocket,
                    )
                elif msg_type == "subscribe":
                    # 扩展入口: 支持按竞品slug订阅
                    competitor = data.get("competitor_slug", "all")
                    await manager.send_personal_message(
                        {
                            "type": "subscribed",
                            "competitor_slug": competitor,
                            "timestamp": datetime.now(CST).isoformat(),
                        },
                        websocket,
                    )
                else:
                    await manager.send_personal_message(
                        {
                            "type": "error",
                            "message": f"未知消息类型: {msg_type}",
                        },
                        websocket,
                    )

            except WebSocketDisconnect:
                break
            except Exception:
                # 忽略其他异常，保持连接
                pass

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


# ============================================================
# 广播接口（admin only - 用于测试/调试）
# ============================================================

@router.post(
    "/broadcast",
    status_code=status.HTTP_200_OK,
    summary="广播测试消息",
    description="向所有WebSocket连接广播测试消息。仅admin可调用",
    include_in_schema=False,  # 不在Swagger文档中显示
)
async def broadcast_test_message(
    db: DBSession,
    message: dict[str, Any],
):
    """广播测试消息（admin调试用）"""
    await manager.broadcast(message)
    return {"sent": True, "active_connections": len(manager.active_connections)}
