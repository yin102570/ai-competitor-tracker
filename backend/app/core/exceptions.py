"""
统一异常体系 - 对齐阶段四设计文档的16个错误码
所有API错误响应遵循统一格式：
{
    "error_code": "AUTH_INVALID_CREDENTIALS",
    "message": "用户名或密码错误",
    "detail": {},
    "request_id": "req_xxx",
    "timestamp": "2026-07-11T10:30:00+08:00"
}
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse


# === 时区定义 ===
CST = timezone(timedelta(hours=8))


class ErrorCode(str, Enum):
    """错误码枚举 - 对齐设计文档 §6 错误码体系"""

    # --- 认证类 (401) ---
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_API_KEY_INVALID = "AUTH_API_KEY_INVALID"
    AUTH_API_KEY_EXPIRED = "AUTH_API_KEY_EXPIRED"

    # --- 授权类 (403) ---
    AUTH_PERMISSION_DENIED = "AUTH_PERMISSION_DENIED"
    AUTH_QUOTA_EXCEEDED = "AUTH_QUOTA_EXCEEDED"

    # --- 资源类 (404) ---
    NOT_FOUND_COMPETITOR = "NOT_FOUND_COMPETITOR"
    NOT_FOUND_USER = "NOT_FOUND_USER"
    NOT_FOUND_SENTIMENT = "NOT_FOUND_SENTIMENT"
    NOT_FOUND_SPIDER_TASK = "NOT_FOUND_SPIDER_TASK"

    # --- 冲突类 (409) ---
    CONFLICT_DUPLICATE = "CONFLICT_DUPLICATE"

    # --- 业务类 (422) ---
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SPIDER_RATE_LIMIT = "SPIDER_RATE_LIMIT"
    DEEPSEEK_API_ERROR = "DEEPSEEK_API_ERROR"

    # --- 系统类 (500) ---
    INTERNAL_ERROR = "INTERNAL_ERROR"


# 错误码到HTTP状态码的映射
_ERROR_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.AUTH_INVALID_CREDENTIALS: 401,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_TOKEN_INVALID: 401,
    ErrorCode.AUTH_API_KEY_INVALID: 401,
    ErrorCode.AUTH_API_KEY_EXPIRED: 401,
    ErrorCode.AUTH_PERMISSION_DENIED: 403,
    ErrorCode.AUTH_QUOTA_EXCEEDED: 403,
    ErrorCode.NOT_FOUND_COMPETITOR: 404,
    ErrorCode.NOT_FOUND_USER: 404,
    ErrorCode.NOT_FOUND_SENTIMENT: 404,
    ErrorCode.NOT_FOUND_SPIDER_TASK: 404,
    ErrorCode.CONFLICT_DUPLICATE: 409,
    ErrorCode.VALIDATION_FAILED: 422,
    ErrorCode.SPIDER_RATE_LIMIT: 422,
    ErrorCode.DEEPSEEK_API_ERROR: 422,
    ErrorCode.INTERNAL_ERROR: 500,
}


class AppException(Exception):
    """
    应用层统一异常基类
    所有业务异常必须继承此类，确保错误响应格式一致
    """

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        detail: dict[str, Any] | None = None,
    ):
        self.error_code = error_code
        self.message = message
        self.detail = detail or {}
        super().__init__(message)

    @property
    def status_code(self) -> int:
        return _ERROR_HTTP_STATUS.get(self.error_code, 500)

    def to_response(self, request_id: str | None = None) -> dict[str, Any]:
        """转换为统一错误响应体"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "detail": self.detail,
            "request_id": request_id or f"req_{uuid.uuid4().hex[:12]}",
            "timestamp": datetime.now(CST).isoformat(),
        }


# === 便捷异常工厂 ===

class AuthError:
    """认证相关异常工厂"""

    @staticmethod
    def invalid_credentials() -> AppException:
        return AppException(
            ErrorCode.AUTH_INVALID_CREDENTIALS,
            "用户名或密码错误",
        )

    @staticmethod
    def token_expired() -> AppException:
        return AppException(
            ErrorCode.AUTH_TOKEN_EXPIRED,
            "访问令牌已过期，请刷新",
        )

    @staticmethod
    def token_invalid() -> AppException:
        return AppException(
            ErrorCode.AUTH_TOKEN_INVALID,
            "访问令牌无效",
        )

    @staticmethod
    def api_key_invalid() -> AppException:
        return AppException(
            ErrorCode.AUTH_API_KEY_INVALID,
            "API Key 无效或已吊销",
        )

    @staticmethod
    def api_key_expired() -> AppException:
        return AppException(
            ErrorCode.AUTH_API_KEY_EXPIRED,
            "API Key 已过期",
        )

    @staticmethod
    def permission_denied(required_role: str) -> AppException:
        return AppException(
            ErrorCode.AUTH_PERMISSION_DENIED,
            f"权限不足，需要角色: {required_role}",
            {"required_role": required_role},
        )

    @staticmethod
    def quota_exceeded(used: int, quota: int) -> AppException:
        return AppException(
            ErrorCode.AUTH_QUOTA_EXCEEDED,
            f"每日配额已用尽（{used}/{quota}）",
            {"used": used, "quota": quota},
        )


class NotFoundError:
    """资源不存在异常工厂"""

    @staticmethod
    def competitor(slug: str) -> AppException:
        return AppException(
            ErrorCode.NOT_FOUND_COMPETITOR,
            "竞品不存在",
            {"slug": slug},
        )

    @staticmethod
    def user(user_id: int | str) -> AppException:
        return AppException(
            ErrorCode.NOT_FOUND_USER,
            "用户不存在",
            {"user_id": user_id},
        )

    @staticmethod
    def sentiment(sentiment_id: int) -> AppException:
        return AppException(
            ErrorCode.NOT_FOUND_SENTIMENT,
            "舆情记录不存在",
            {"sentiment_id": sentiment_id},
        )

    @staticmethod
    def spider_task(task_id: str) -> AppException:
        return AppException(
            ErrorCode.NOT_FOUND_SPIDER_TASK,
            "爬虫任务不存在",
            {"task_id": task_id},
        )


class BusinessError:
    """业务逻辑异常工厂"""

    @staticmethod
    def duplicate(field: str, value: str) -> AppException:
        return AppException(
            ErrorCode.CONFLICT_DUPLICATE,
            f"资源已存在：{field} = {value}",
            {"field": field, "value": value},
        )

    @staticmethod
    def validation_failed(errors: list[dict]) -> AppException:
        return AppException(
            ErrorCode.VALIDATION_FAILED,
            "数据验证失败",
            {"errors": errors},
        )

    @staticmethod
    def spider_rate_limit(retry_after: int) -> AppException:
        return AppException(
            ErrorCode.SPIDER_RATE_LIMIT,
            f"爬虫频率限制，{retry_after}秒后重试",
            {"retry_after": retry_after},
        )

    @staticmethod
    def deepseek_api_error(detail: str) -> AppException:
        return AppException(
            ErrorCode.DEEPSEEK_API_ERROR,
            f"DeepSeek API 调用失败: {detail}",
        )

    @staticmethod
    def internal_error(detail: str = "") -> AppException:
        return AppException(
            ErrorCode.INTERNAL_ERROR,
            "服务器内部错误",
            {"detail": detail} if detail else {},
        )


# === FastAPI 异常处理器 ===

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """处理 AppException，返回统一格式错误响应"""
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response(request_id),
        headers={"X-Request-ID": request_id or ""} if request_id else {},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底处理未捕获异常，避免泄露堆栈信息"""
    request_id = getattr(request.state, "request_id", None)
    app_exc = BusinessError.internal_error(str(exc) if settings.is_development else "")
    return JSONResponse(
        status_code=500,
        content=app_exc.to_response(request_id),
    )


# 延迟导入避免循环引用
from app.core.config import settings
