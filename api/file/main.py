from enum import Enum
from typing import Any, Optional, List
# from redis import asyncio as aioredis
from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi_cache import FastAPICache
from starlette.background import BackgroundTasks
from api.file.utils import *
from api.users.models import User, File, FileChunk
from api.users.utils import get_current_user
from utils.dependencies import get_redis_connection

parts_list = []
file_router = APIRouter()
parts_info_dict = {}
file_list_info = []


class FilePreUploadRequest(BaseModel):
    file_hash: str
    file_size: int
    file_name: str


class FilePreUploadResponse(BaseModel):
    file_id: int
    status: str
    uploaded_chunks: Optional[List[int]] = []


class FileStatus(Enum):
    UPLOADING = 'uploading'
    COMPLETE = 'complete'


@file_router.post("/pre_upload", response_model=FilePreUploadResponse)
async def file_pre_upload(file_info: FilePreUploadRequest, current_user: User = Depends(get_current_user)):
    # 检查是否存在具有相同 file_hash 的文件记录
    existing_file = await File.filter(file_hash=file_info.file_hash).prefetch_related("chunks").first()
    if existing_file:
        if existing_file.status == 'uploading':
            # 返回未上传的分片列表
            uploaded_chunks = sorted([chunk.chunk_num for chunk in existing_file.chunks])
            return FilePreUploadResponse(file_id=existing_file.id, status="partial_upload",
                                         uploaded_chunks=uploaded_chunks)
        elif existing_file.status == 'completed':
            # 返回文件信息
            return FilePreUploadResponse(file_id=existing_file.id, status="completed", uploaded_chunks=[])
    else:
        # 创建新的文件记录
        new_file = await File.create(file_hash=file_info.file_hash, status='uploading', user_id=current_user.id,
                                     file_size=file_info.file_size, filename=file_info.file_name)
        return FilePreUploadResponse(file_id=new_file.id, status="new_upload", uploaded_chunks=[])


@file_router.post("/upload", response_model=dict)
async def upload_chunk(background_tasks: BackgroundTasks,
                       chunk_info: ChunkUploadInfo = Depends(),
                       current_user: User = Depends(get_current_user),
                       redis=Depends(get_redis_connection)) -> dict[str, Any]:
    try:
        context_data = await get_or_create_upload_context(chunk_info, redis, current_user)
        background_tasks.add_task(process_chunk_task.s(chunk_info.dict(), redis, current_user, context_data))
        return {"status": "success", "data": {"file_name": chunk_info.file_name, "chunk_index": chunk_info.chunk_number}}
    except Exception as e:
        logger.error(f"Error processing chunk: {str(e)}")
        return {"status": "error", "message": "Internal Server Error", "code": 500}


@file_router.post("/complete_upload/", response_model=dict)
async def complete_upload(file_hash: str, background_tasks: BackgroundTasks,
                          current_user: User = Depends(get_current_user)):
    await FileChunk.filter(file_hash=file_hash)
    return {"status": "merging"}
