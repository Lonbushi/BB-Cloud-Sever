from fastapi.routing import APIRouter
from typing import Optional
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from fastapi import File, BackgroundTasks
from tortoise.transactions import in_transaction

from api.users.utils import *

user_router = APIRouter()

region_name = "eu-north-1"
bucket_name = "upimgpredict"


# 令牌响应模型，包含访问令牌、刷新令牌及其类型
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# 用于提取令牌数据的模型，如用户名
class TokenData(BaseModel):
    username: Union[str, None] = None


# 用户注册信息的模型，包含用户名、密码、邮箱等字段
class UserRegister(BaseModel):  # 注册模型字段
    username: str
    password: str
    email: Union[str, None] = None  # 可选字段
    nick_name: str
    avatar: Optional[str] = None
    create_time: datetime


# 获取用户信息模型
class UserInfo(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    nick_name: Optional[str] = None
    avatar: Optional[str] = None
    create_time: Optional[datetime] = None
    # role: str = "超级管理者"  # 0为管理者 1为员工
    disabled: bool = False  # 控制账户是否被禁用
    phone_num: Optional[int] = None


# 用户头像
class UserAvatar(BaseModel):
    avatar: str


# 登录接口
@user_router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
        # 生成 access token
    access_token, _, access_token_expires, _ = create_tokens(user)
    existing_refresh_token = await RefreshToken.filter(user=user, is_revoked=False).first()
    if existing_refresh_token and existing_refresh_token.expires_at > datetime.now(timezone.utc):
        # 如果存在有效的 refresh token，则使用它
        refresh_token = existing_refresh_token.token
    else:
        # 否则，生成新的 refresh token 并保存到数据库
        _, refresh_token, _, refresh_token_expires = create_tokens(user)
        await save_refresh_token_to_db(user=user, refresh_token=refresh_token,
                                       refresh_token_expires=refresh_token_expires)

    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}


# 刷新token接口
@user_router.post("/refresh")
async def refresh_token(refresh_request: RefreshTokenRequest):
    # 验证传入的 refresh token 是否有效且未过期
    existing_refresh_token = await RefreshToken.filter(token=refresh_request.refresh_token, is_revoked=False).first()
    if existing_refresh_token is None or existing_refresh_token.expires_at <= datetime.now(timezone.utc):
        # 如果 refresh token 无效或已过期，抛出异常
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    payload = jwt.decode(refresh_request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
    username = payload.get("sub")
    user = await User.get(username=username)
    # 假设 REFRESH_TOKEN_EXPIRE_MINUTES 是整数，表示刷新令牌有效期的分钟数
    refresh_token_threshold = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    # 生成新的 access token
    new_access_token, _, _, _ = create_tokens(user)
    # 检查现有的 refresh token 是否即将过期，如果是，则生成新的 refresh token
    if existing_refresh_token.expires_at - datetime.now(timezone.utc) < refresh_token_threshold:
        # 生成新的 refresh token 并保存到数据库
        _, new_refresh_token, _, refresh_token_expires = create_tokens(user)
        await save_refresh_token_to_db(user, new_refresh_token, refresh_token_expires)
    else:
        # 如果现有的 refresh token 未即将过期，继续使用它
        new_refresh_token = existing_refresh_token.token

    return {"access_token": new_access_token, "refresh_token": new_refresh_token, "token_type": "bearer"}


# 注册接口
@user_router.post("/register", response_model=Token)  # 确保 Token 模型包含 access_token 和 refresh_token 字段
async def register_user(user_data: UserRegister):
    # 检查用户名是否已存在
    existing_user = await User.get_or_none(username=user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # 散列用户密码
    hashed_password = pwd_context.hash(user_data.password)

    # 创建新用户并保存到数据库
    user = User(username=user_data.username, password_hash=hashed_password, email=user_data.email)
    await user.save()
    access_token, refresh_token, _, refresh_token_expires = create_tokens(user)
    await save_refresh_token_to_db(user, refresh_token, refresh_token_expires)

    # 返回新创建的访问令牌和刷新令牌
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


# 获取用户信息
@user_router.get("/me", response_model=UserInfo)
async def read_user_me(current_user: User = Depends(get_current_user)):
    """
    获取当前认证用户的信息
    """
    if current_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return current_user


# 定义上传头像接口
@user_router.post("/avatar", response_model=UserAvatar)
async def create_upload_avatar(background_tasks: BackgroundTasks, file: UploadFile = File(...),
                               current_user: User = Depends(get_current_active_user)):
    if not file.filename.endswith(('.png', '.jpg', '.jpeg', 'gif')):
        raise HTTPException(status_code=400, detail="Invalid file format")

    # 使用后台任务来处理文件保存和数据库更新，以免阻塞请求
    avatar_path = await handle_upload_file(file, current_user.username)

    uploaded_image_url = f"https://{bucket_name}.s3.{region_name}.amazonaws.com/{avatar_path}"
    # 使用Tortoise ORM的.filter()和.update()方法来更新数据库中的用户记录
    async with in_transaction():
        updated_count = await User.filter(id=current_user.id).update(avatar=uploaded_image_url)
    if updated_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    # 返回更新后的头像URL
    return {"avatar": uploaded_image_url}
