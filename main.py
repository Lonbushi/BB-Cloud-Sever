from fastapi_cache.backends.redis import RedisBackend
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from starlette.websockets import WebSocket, WebSocketDisconnect
from api.file.main import file_router
from api.folder.main import folder_router
from api.users.main import user_router
from tortoise.contrib.fastapi import register_tortoise
from setting import TORTOISE_ORM
from fastapi_cache.decorator import cache

from utils.dependencies import get_redis_connection, close_redis_connection

app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://10.185.68.76:9528/"
]
register_tortoise(
    app=app,
    config=TORTOISE_ORM
)


@app.on_event("startup")
async def startup_event():
    # 确保在应用启动时初始化 Redis 连接池
    await get_redis_connection()


@app.on_event("shutdown")
async def shutdown_event():
    # 关闭 Redis 连接池
    await close_redis_connection()


app.include_router(user_router, prefix='/user', tags=['用户接口'])
app.include_router(folder_router, prefix='/folder', tags=['文件夹接口'])
app.include_router(file_router, prefix='/file', tags=['文件接口'])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # *：代表所有客户端
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == '__main__':
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
