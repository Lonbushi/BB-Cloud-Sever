import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Union
import aioboto3
from fastapi import Depends, HTTPException, UploadFile
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from starlette import status

from api.users.models import User, RefreshToken

# 定义JWT令牌的密钥、加密算法和令牌过期时间
SECRET_KEY = "ecea1af2549498c2db45fd896698082a149d3eb8a7d5eda20e599c31093e0260"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_MINUTES = 7
region_name = "eu-north-1"
bucket_name = "upimgpredict"
# 密码加密上下文配置，使用bcrypt算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2的密码流令牌获取URL配置
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_user(username: str):
    return await User.get(username=username)


# 验证明文密码和散列密码是否匹配
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# 验证用户身份的异步函数
async def authenticate_user(username: str, password: str):
    user = await get_user(username)
    if not user or not verify_password(password, user.password_hash):
        return False
    return user


# 创建访问令牌的函数，可以设置令牌的过期时间
def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# 生成 Access Token 和 Refresh Token 的函数
def create_tokens(user: User):
    # 生成 access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # 生成 refresh token
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_MINUTES)  # 假设 refresh token 有效期为7天
    refresh_token = create_refresh_token(
        data={"sub": user.username}, expires_delta=refresh_token_expires
    )

    return access_token, refresh_token, access_token_expires, refresh_token_expires


# 创建 refresh token令牌的函数，用于刷新token
def create_refresh_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    # 设置一个更长的过期时间，例如7天
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# 保存 Refresh Token 到数据库的函数
async def save_refresh_token_to_db(user: User, refresh_token: str, refresh_token_expires: timedelta):
    new_refresh_token = RefreshToken(
        user=user,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc) + refresh_token_expires,
        is_revoked=False
    )
    await new_refresh_token.save()


# 验证 Refresh Token 是否有效的函数
async def validate_refresh_token(refresh_token: str):
    db_token = await RefreshToken.get_or_none(token=refresh_token, is_revoked=False)
    if db_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or revoked",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return db_token


# 获取当前用户的异步函数，从令牌中提取用户信息
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                          detail="Could not validate credentials",
                                          headers={"WWW-Authenticate": "Bearer"}, )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        user = await get_user(username)
        if user is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return user


# 获取当前活跃用户的异步函数，检查用户是否被禁用
async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def handle_upload_file(upload_file: UploadFile, username: str):
    # 获取上传文件的扩展名
    _, extension = os.path.splitext(upload_file.filename)
    # 生成唯一的文件名，但保留原始文件的扩展名
    unique_filename = f"uploads/{username}_{uuid.uuid4()}{extension}"
    # 读取上传文件的内容
    file_content = await upload_file.read()
    upload_file.file.seek(0)  # 重置文件指针，以便文可以被重新读取
    # 创建 aioboto3 session
    session = aioboto3.Session()
    # 异步上传到 AWS S3
    async with session.client('s3', region_name=region_name) as s3_client:
        await s3_client.put_object(Bucket=bucket_name, Key=unique_filename, Body=file_content)

    return unique_filename
