from datetime import datetime
from typing import Optional, List
from fastapi import Depends, APIRouter
from pydantic import BaseModel
from api.folder.utils import *
from api.users.models import Folder, User
from api.users.utils import get_current_user

folder_router = APIRouter()


class FolderCreate(BaseModel):
    id: Optional[int] = None
    name: str
    parent: Optional[int] = None


class FolderInfoList(BaseModel):
    id: int
    name: str
    path: str
    parent: Optional[int] = None
    user_id: int
    is_deleted: bool
    create_time: datetime
    update_time: datetime

    class Config:
        from_attributes = True  # 设置 orm_mode 为 True


class FolderRenameRequest(BaseModel):
    new_name: str


class FolderInfo(BaseModel):
    id: int
    name: str
    path: str
    parent: Optional[int] = None
    children: Optional[List['FolderInfo']] = None  # 使用Optional和List来定义children


FolderInfo.update_forward_refs()  # 更新模型以识别自引用


# 主要API函数
@folder_router.post("/", response_model=FolderCreate)
async def create_folder(folder_data: FolderCreate, current_user: User = Depends(get_current_user)):
    # 检查父文件夹是否存在
    parent_folder = await get_parent_folder(folder_data.parent, current_user)

    # 根据父文件夹设置新文件夹的路径和名称
    base_path = "/新建文件夹" if parent_folder is None else f"{parent_folder.path}/{folder_data.name}"
    new_folder_path = await create_unique_folder_path(base_path=base_path, user=current_user)
    base_name = "新建文件夹" if parent_folder is None else folder_data.name
    new_folder_name = await create_unique_folder_name(base_name=base_name, parent=parent_folder, user=current_user)
    # 创建新文件夹
    folder = await Folder.create(
        name=new_folder_name,
        path=new_folder_path,
        parent=parent_folder,
        user=current_user
    )

    return FolderCreate(
        id=folder.id,
        name=folder.name,
        path=folder.path,
        parent=folder.parent.id if folder.parent else None
    )


@folder_router.get('/', response_model=List[FolderInfo])
async def get_folders(parent_id: Optional[int] = None):
    if parent_id is not None:
        root_folders = await Folder.filter(id=parent_id).filter()
    else:
        root_folders = await Folder.filter(parent_id=parent_id).all()

    async def build_folder_tree(parent_folder):
        children_folders = await Folder.filter(parent_id=parent_folder.id).all()
        children = [await build_folder_tree(child) for child in children_folders]

        return FolderInfo(
            id=parent_folder.id,
            name=parent_folder.name,
            path=parent_folder.path,
            parent=parent_folder.parent_id,
            children=children if children else None  # 设置children字段，如果没有子文件夹则为None
        )

    routes = [await build_folder_tree(folder) for folder in root_folders]
    return routes


@folder_router.delete('/{folder_id}')
async def delete_folders(folder_id: int, current_user: User = Depends(get_current_user)):
    deleted_count = await Folder.filter(id=folder_id, user=current_user).delete()
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"folder {folder_id} not found")
    return {}


@folder_router.put('/{folder_id}')
async def rename_folders(folder_id: int, request: FolderRenameRequest, current_user: User = Depends(get_current_user)):
    folder = await Folder.filter(id=folder_id, user=current_user).first()

    if folder is None:
        raise HTTPException(status_code=404, detail=f"Folder {folder_id} not found")
        # 更新文件夹名称
    folder.name = request.new_name
    print(folder.name)
    # 如果文件夹有父文件夹，获取父文件夹路径，否则使用根路径
    if folder.parent_id:
        parent_path = await get_parent_folder_path(folder.parent_id)
        folder.path = f"{parent_path}/{request.new_name}"
    else:
        folder.path = f"/{request.new_name}"

    # 保存更改
    await folder.save()

    # 返回更新后的文件夹信息
    return {
        "id": folder.id,
        "name": folder.name,
        "path": folder.path,
        "parent": folder.parent_id if folder.parent_id else None
    }
