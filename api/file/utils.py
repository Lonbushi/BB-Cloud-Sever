import json
import os
import logging
import mimetypes
from contextvars import ContextVar
from urllib.parse import quote, unquote
import aioboto3
from datetime import datetime

import asyncio
from fastapi import UploadFile
from pydantic import BaseModel
from celery import Celery
from contextlib import asynccontextmanager
from api.users.models import File, FileChunk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
region_name = "eu-north-1"
bucket_name = "upimgpredict"
# 使用 ContextVar 来存储请求作用域内的数据
upload_context = ContextVar('upload_context')
app = Celery('tasks', broker='redis://localhost:6379/0')


# 假设的分块上传信息模型
class ChunkUploadInfo(BaseModel):
    chunk: UploadFile
    file_name: str
    total: int
    file_hash: str
    chunk_hash: str
    chunk_number: int
    chunk_size: int
    file_id: int


def generate_unique_key(file_name: str, file_hash: str, current_user) -> str:
    file_datetime = datetime.now().strftime('%Y-%m-%d')
    _, ext = os.path.splitext(file_name)
    return f"{file_datetime}/{current_user.id}/{file_hash}{ext}"


async def init_multipart_upload(file_name: str, file_hash: str, current_user):
    key = generate_unique_key(file_name, file_hash, current_user)
    session = aioboto3.Session()
    try:
        async with session.client('s3', region_name=region_name) as s3_client:
            response = await s3_client.create_multipart_upload(Bucket=bucket_name, Key=key)
            return response['UploadId'], key
    except Exception as e:
        logger.error(f"Error initializing multipart upload: {str(e)}")
        raise


@asynccontextmanager
async def get_upload_context(file_hash: str, chunk_hash: str, redis):
    upload_key = chunk_hash
    context = {'upload_key': upload_key, 'parts_list': [], 'redis': redis}
    token = upload_context.set(context)
    try:
        yield context
    finally:
        upload_context.reset(token)
        await update_upload_metadata_to_database(file_hash, chunk_hash, redis)


async def update_upload_metadata_to_database(file_hash, key, upload_id):
    file = await File.filter(file_hash=file_hash).first()
    if file:
        file.upload_id = upload_id
        file.key = key
        await file.save()
    else:
        await File.create(file_hash=file_hash, upload_id=upload_id, key=key)


async def handle_chunk(chunk_info, key, upload_id, max_retries=3, retry_delay=2):
    session = aioboto3.Session()
    chunk_data = await chunk_info.chunk.read()
    chunk_num = chunk_info.chunk_number
    for attempt in range(max_retries):
        try:
            async with session.client('s3', region_name=region_name) as s3_client:
                part_upload = await s3_client.upload_part(
                    Bucket=bucket_name,
                    Key=key,
                    UploadId=upload_id,
                    PartNumber=chunk_num + 1,
                    Body=chunk_data
                )
            return {'ETag': part_upload['ETag'], 'PartNumber': chunk_num + 1}
        except Exception as e:
            logger.error(f"上传分块 {chunk_num} 失败(尝试 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                raise


async def process_chunk(chunk_info, key, upload_id, total_chunks):
    try:
        part = await handle_chunk(chunk_info, key, upload_id)
        if 'ETag' not in part:
            raise Exception(f'无效的分块响应: {part}')
        ctx = upload_context.get()
        parts_list = ctx['parts_list']
        logger.info(f"parts_list{parts_list}")
        part_num = part['PartNumber']
        if part_num not in [p['PartNumber'] for p in parts_list if p is not None]:
            parts_list.append(part)
            upload_key = ctx['upload_key']
            await ctx['redis'].rpush(f'{upload_key}:parts', json.dumps(part))
        return len(parts_list) == total_chunks
    except Exception as e:
        logger.error(f'处理分块出错: {e}')
        return False


async def check_upload_status(file_name, file_hash, redis, current_user, chunk_index):
    upload_id, key = await check_upload_exists(file_name, file_hash, redis, current_user, chunk_index)
    if upload_id is None and key is None and chunk_index != 0:
        cached_data = await redis.hgetall(file_hash)
        upload_id = cached_data.get('upload_id')
        key = cached_data.get('key')
        logger.info(f"upload_id{upload_id},key{key}")
    return upload_id, key


@app.task
async def check_upload_exists(file_name: str, file_hash: str, redis, current_user, chunk_num):
    # 检查缓存中是否存在upload_id和key
    cached_data = await redis.hgetall(file_hash)
    logger.info(f"缓存中的数据：{cached_data}")
    if cached_data:
        upload_id = cached_data.get('upload_id')
        key = cached_data.get('key')
        logger.info(f"缓存中的返回数据{upload_id}，{key}")
        return upload_id, key
    if chunk_num == 0:
        file = await File.filter(file_hash=file_hash).first()
        if file is None or (file.upload_id is None and file.key is None):
            upload_id, key = await init_multipart_upload(file_name, file_hash, current_user)
            await redis.hmset(file_hash, {"upload_id": upload_id, "key": key})
        else:
            upload_id = file.upload_id
            key = file.key

        logger.info(f"upload:{upload_id}")
        return upload_id, key
    else:
        # 如果不是第一个分片,直接返回None
        return None, None


@app.task
async def save_chunk_Etag(file_hash, parts_list, redis):
    upload_key = f"{file_hash}:upload"
    for part in parts_list:
        await redis.lpush(upload_key, json.dumps(part))


async def update_cache_to_database(file_hash, redis):
    cached_data = await redis.hgetall(file_hash)
    upload_id = cached_data.get('upload_id')
    key = cached_data.get('key')
    file = await File.filter(file_hash=file_hash).first()
    if file:
        file.upload_id = upload_id
        file.key = key
        await file.save()
    else:
        # 如果文件记录不存在,创建新的文件记录
        await File.create(file_hash=file_hash, upload_id=upload_id, key=key)
    await redis.delete(file_hash)


def generate_file_path(key: str) -> str:
    file_path = f"https://{bucket_name}.s3.{region_name}.amazonaws.com/{key}"
    return unquote(file_path, encoding='utf-8')


async def save_file_metadata(file_hash: str, key: str, filename: str, total_num: int):
    file_path = generate_file_path(key)
    file_type = get_mime_type(filename)
    try:
        file_record = await File.get(file_hash=file_hash)
        if file_record:
            file_record.file_path = file_path
            file_record.file_type = file_type
            file_record.status = "completed"
            file_record.total_num = total_num
            await file_record.save()
            logger.info(f"文件元数据更新成功: {file_hash}")
        else:
            logger.warning(f"文件记录不存在: {file_hash}")
    except Exception as e:
        logger.error(f"文件元数据更新失败: {file_hash}, 错误: {str(e)}")
        raise


async def complete_multipart_upload(chunk_hash: str, file_hash: str, upload_id: str, key: str,
                                    filename: str, total_num: int, redis):
    upload_key = chunk_hash
    session = aioboto3.Session()
    parts_list = await redis.lrange(f'{upload_key}:parts', 0, -1)
    parts = sorted([json.loads(part) for part in parts_list], key=lambda x: x['PartNumber'])
    logger.info(f"正序排列之后的part列表：{parts}")
    try:
        async with session.client('s3', region_name=region_name) as s3_client:
            await s3_client.complete_multipart_upload(
                Bucket=bucket_name,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts}
            )
            # 文件上传完成后，保存文件元数据到数据库
        await save_file_metadata(file_hash, key, filename, total_num)
        await update_upload_metadata_to_database(file_hash, key, upload_id)
        await redis.delete(upload_key)
        await redis.delete(f'{upload_key}:parts')
    except Exception as e:
        logger.error(f"Error completing multipart upload: {str(e)}")
        raise


async def get_upload_context_data(file_hash, chunk_hash, redis):
    try:
        async with get_upload_context(file_hash, chunk_hash, redis) as ctx:
            upload_key = ctx['upload_key']
            logger.info(f"upload_key的结果{upload_key}")

            result = await redis.hmget(upload_key, 'upload_id', 'key')
            logger.info(f"redis.hmget的结果: {result}")

            upload_id, key = result
            if not upload_id or not key:
                logger.warning(f"upload_id或key不存在: upload_id={upload_id}, key={key}")
                return None

            return {'upload_id': upload_id, 'key': key}
    except Exception as e:
        logger.exception(f"在get_upload_context_data函数中发生错误: {str(e)}")
        return None


async def get_or_create_upload_context(chunk_info, redis, current_user):
    context_data = await get_upload_context_data(chunk_info.file_hash, chunk_info.chunk_hash, redis)
    logger.info(f"context_data:{context_data}")
    if context_data is None:
        upload_id, key = await init_multipart_upload(chunk_info.file_name, chunk_info.file_hash, current_user)
        logger.info(f"upload_id:{upload_id}, key:{key}")
        await redis.hmset(chunk_info.chunk_hash, {'upload_id': upload_id, 'key': key})
        context_data = {'upload_id': upload_id, 'key': key}
    return context_data


@app.task(bind=True, max_retries=3)
async def process_chunk_task(self, chunk_info: dict, redis, current_user, context_data):
    try:
        chunk_info = ChunkUploadInfo(**chunk_info)
        logger.info(f"chunk_info的数据是：{chunk_info}")
        save_chunk = await process_chunk(chunk_info, context_data['key'], context_data['upload_id'], chunk_info.total)
        if save_chunk:
            await complete_multipart_upload(chunk_info.chunk_hash, chunk_info.file_hash, context_data['upload_id'],
                                            context_data['key'], chunk_info.file_name, chunk_info.total, redis)
    except Exception as e:
        logger.error(f"Error processing chunk: {str(e)}")
        raise self.retry(exc=e, countdown=2)


def get_mime_type(filename: str) -> str:
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or 'application/octet-stream'
