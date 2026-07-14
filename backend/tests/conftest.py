"""
Pytest 全局夹具 - 测试数据库、测试客户端、测试用户、Mock工具
使用内存SQLite，测试间隔离
增强: 多角色用户 / API Key / 配额状态 / Mock Redis / 性能计时
"""

import pytest
import pytest_asyncio
import time
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.core.security import hash_password, generate_api_key
from app.models.user import User, UserRole, APIKey
from app.main import create_app


# === 测试数据库引擎（内存SQLite） ===
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """每个测试函数独立的数据库会话"""
    # 建表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 提供会话
    async with test_session_factory() as session:
        yield session
        await session.rollback()

    # 清表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ============================================================
# 用户工厂 fixtures
# ============================================================

@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """创建测试admin用户"""
    user = User(
        email="test@example.com",
        password_hash=hash_password("TestPassword123!"),
        name="测试管理员",
        role=UserRole.ADMIN.value,
        daily_quota=100,
        quota_used=0,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_analyst(db_session: AsyncSession) -> User:
    """创建测试analyst用户"""
    user = User(
        email="analyst@example.com",
        password_hash=hash_password("AnalystPass123!"),
        name="测试分析师",
        role=UserRole.ANALYST.value,
        daily_quota=100,
        quota_used=0,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_viewer(db_session: AsyncSession) -> User:
    """创建测试viewer用户"""
    user = User(
        email="viewer@example.com",
        password_hash=hash_password("ViewerPass123!"),
        name="测试观察者",
        role=UserRole.VIEWER.value,
        daily_quota=5,
        quota_used=0,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_user_quota_exhausted(db_session: AsyncSession) -> User:
    """创建配额耗尽的测试用户"""
    user = User(
        email="noquota@example.com",
        password_hash=hash_password("NoQuota123!"),
        name="配额耗尽用户",
        role=UserRole.VIEWER.value,
        daily_quota=5,
        quota_used=5,  # 已用完
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_inactive_user(db_session: AsyncSession) -> User:
    """创建已禁用的测试用户"""
    user = User(
        email="inactive@example.com",
        password_hash=hash_password("Inactive123!"),
        name="已禁用用户",
        role=UserRole.VIEWER.value,
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ============================================================
# API Key fixtures
# ============================================================

@pytest_asyncio.fixture(scope="function")
async def test_api_key(db_session: AsyncSession, test_user: User) -> tuple[str, APIKey]:
    """创建测试API Key，返回(明文key, APIKey对象)"""
    plaintext, key_hash, key_prefix = generate_api_key()
    api_key = APIKey(
        user_id=test_user.id,
        name="测试密钥",
        key_hash=key_hash,
        key_prefix=key_prefix,
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()
    await db_session.refresh(api_key)
    return plaintext, api_key


@pytest_asyncio.fixture(scope="function")
async def api_key_headers(test_api_key: tuple[str, APIKey]) -> dict:
    """API Key认证请求头"""
    return {"X-API-Key": test_api_key[0]}


# ============================================================
# 客户端 fixtures
# ============================================================

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    """测试HTTP客户端"""
    app = create_app()

    # 覆盖数据库依赖
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def auth_token(client: AsyncClient, test_user: User) -> str:
    """获取admin用户的JWT访问令牌"""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "TestPassword123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def auth_headers(auth_token: str) -> dict:
    """JWT认证请求头"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest_asyncio.fixture(scope="function")
async def analyst_token(client: AsyncClient, test_analyst: User) -> str:
    """获取analyst用户的JWT访问令牌"""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "analyst@example.com", "password": "AnalystPass123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def analyst_headers(analyst_token: str) -> dict:
    """analyst认证请求头"""
    return {"Authorization": f"Bearer {analyst_token}"}


@pytest_asyncio.fixture(scope="function")
async def viewer_token(client: AsyncClient, test_viewer: User) -> str:
    """获取viewer用户的JWT访问令牌"""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@example.com", "password": "ViewerPass123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest_asyncio.fixture(scope="function")
async def viewer_headers(viewer_token: str) -> dict:
    """viewer认证请求头"""
    return {"Authorization": f"Bearer {viewer_token}"}


# ============================================================
# 性能计时 fixture
# ============================================================

@pytest.fixture
def perf_timer():
    """性能计时器 - 返回函数，调用后返回毫秒数"""
    timings: list[float] = []

    class Timer:
        def __init__(self):
            self._start = time.perf_counter()

        def elapsed_ms(self) -> float:
            return (time.perf_counter() - self._start) * 1000

        def check(self, max_ms: float) -> float:
            """检查是否在最大时间内完成，返回实际耗时"""
            elapsed = self.elapsed_ms()
            timings.append(elapsed)
            return elapsed

    timer = Timer()
    yield timer
    # 不自动断言，由测试决定阈值


# ============================================================
# Mock Redis fixture（用于无Redis环境的测试）
# ============================================================

@pytest_asyncio.fixture(scope="function")
async def mock_redis(monkeypatch):
    """Mock Redis，避免测试依赖真实Redis"""
    _blacklist: set[str] = set()

    class MockRedisClient:
        def __init__(self):
            self._data: dict[str, str] = {}
            self._ttls: dict[str, float] = {}

        async def ping(self):
            return True

        async def get(self, key: str):
            return self._data.get(key)

        async def setex(self, key: str, ttl: int, value: str):
            self._data[key] = value
            self._ttls[key] = ttl

        async def close(self):
            self._data.clear()
            self._ttls.clear()

    mock_client = MockRedisClient()

    async def mock_get_redis():
        return mock_client

    async def mock_is_blacklisted(jti: str) -> bool:
        return jti in _blacklist

    async def mock_add(jti: str, ttl: int) -> None:
        _blacklist.add(jti)

    monkeypatch.setattr("app.core.security.TokenBlacklist._get_redis", mock_get_redis)
    monkeypatch.setattr("app.core.security.TokenBlacklist._redis", mock_client)
    monkeypatch.setattr("app.core.security.TokenBlacklist.is_blacklisted", mock_is_blacklisted)
    monkeypatch.setattr("app.core.security.TokenBlacklist.add", mock_add)
    monkeypatch.setattr("app.core.security.TokenBlacklist.close", lambda: None)

    yield mock_client
    _blacklist.clear()
