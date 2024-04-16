from fastapi import HTTPException
from tortoise.exceptions import DoesNotExist

from api.users.models import Folder, User


async def create_unique_folder_path(base_path: str, user: User) -> str:
    count = 0
    unique_path = base_path
    while await Folder.exists(path=unique_path, user=user):
        count += 1
        unique_path = f"{base_path} ({count})"
    return unique_path


async def create_unique_folder_name(user: User, base_name: str, parent: Folder = None) -> str:
    count = 0
    unique_name = base_name
    while await Folder.exists(name=unique_name, parent=parent, user=user):
        count += 1
        unique_name = f"{base_name}_{count}"
    return unique_name


# 辅助函数：检查父文件夹是否存在，并返回父文件夹对象
async def get_parent_folder(parent_id: int, user: User) -> Folder:
    if parent_id is not None:
        try:
            return await Folder.get(id=parent_id, user=user)
        except DoesNotExist:
            raise HTTPException(status_code=404, detail="Parent folder not found")
    return None


async def get_parent_folder_path(parent_id: int) -> str:
    print(parent_id)
    parent_folder = await Folder.filter(id=parent_id).first()
    if parent_folder:
        return parent_folder.path
    else:
        # 如果没有找到父文件夹，可能返回根路径或抛出异常
        return "/"