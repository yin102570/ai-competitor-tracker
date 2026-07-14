"""
Spiders模块API路由 - 爬虫任务触发、查询、取消、调度配置
路由前缀: /api/v1/spiders

接口清单:
  POST   /trigger            手动触发爬虫任务 (analyst+)
  GET    /tasks/{task_id}    查询任务状态
  GET    /tasks              任务历史列表
  GET    /schedule           调度配置
  DELETE /tasks/{task_id}    取消任务 (analyst+)
"""

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DBSession, PaginationDep
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.spider import (
    SpiderScheduleResponse,
    SpiderTaskListItem,
    SpiderTaskResponse,
    SpiderTriggerRequest,
)
from app.services.spider_service import SpiderService

router = APIRouter(prefix="/spiders", tags=["爬虫调度"])


# ============================================================
# 触发任务
# ============================================================

@router.post(
    "/trigger",
    response_model=SpiderTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="触发爬虫任务",
    description="手动触发爬虫任务。需要analyst或admin权限",
)
async def trigger_task(
    request: SpiderTriggerRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> SpiderTaskResponse:
    """触发爬虫任务"""
    service = SpiderService(db)
    return await service.trigger(request, current_user)


# ============================================================
# 查询任务
# ============================================================

@router.get(
    "/tasks/{task_id}",
    response_model=SpiderTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="查询任务状态",
    description="查询单个爬虫任务的详细状态和结果",
)
async def get_task(
    task_id: str,
    db: DBSession,
) -> SpiderTaskResponse:
    """查询任务状态"""
    service = SpiderService(db)
    return await service.get_task(task_id)


# ============================================================
# 任务列表
# ============================================================

@router.get(
    "/tasks",
    response_model=PaginatedResponse[SpiderTaskListItem],
    status_code=status.HTTP_200_OK,
    summary="任务列表",
    description="爬虫任务历史列表，支持按竞品/类型/状态筛选",
)
async def list_tasks(
    db: DBSession,
    pagination: PaginationDep,
    competitor_slug: str | None = Query(default=None, description="竞品筛选"),
    task_type: str | None = Query(default=None, description="任务类型筛选"),
    status: str | None = Query(default=None, description="状态筛选"),
) -> PaginatedResponse[SpiderTaskListItem]:
    """任务列表"""
    service = SpiderService(db)
    items, total = await service.list_tasks(
        competitor_slug=competitor_slug,
        task_type=task_type,
        status=status,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


# ============================================================
# 调度配置
# ============================================================

@router.get(
    "/schedule",
    response_model=SpiderScheduleResponse,
    status_code=status.HTTP_200_OK,
    summary="调度配置",
    description="获取爬虫调度规则、并发限制、频率限制",
)
async def get_schedule(
    db: DBSession,
) -> SpiderScheduleResponse:
    """调度配置"""
    service = SpiderService(db)
    return await service.get_schedule()


# ============================================================
# 取消任务
# ============================================================

@router.delete(
    "/tasks/{task_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="取消任务",
    description="取消pending状态的爬虫任务。需要analyst或admin权限",
)
async def cancel_task(
    task_id: str,
    db: DBSession,
    current_user: CurrentUser,
) -> SuccessResponse:
    """取消任务"""
    service = SpiderService(db)
    await service.cancel_task(task_id, current_user)
    return SuccessResponse(message=f"任务 {task_id} 已取消")
