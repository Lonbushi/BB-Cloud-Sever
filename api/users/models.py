from tortoise.models import Model
from tortoise import fields
from enum import Enum


class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=32, description="用户名")
    password_hash = fields.CharField(max_length=60, description="密码")
    email = fields.CharField(max_length=255, unique=True, null=True)  # 添加 email 字段
    avatar = fields.CharField(max_length=255, description="头像", null=True)
    nick_name = fields.CharField(max_length=255, default="昵称")
    phone_num = fields.CharField(max_length=16, description="手机号", null=True)
    create_time = fields.DatetimeField(auto_now_add=True, description="注册时间")
    disabled = fields.BooleanField(default=False)  # 控制账户是否被禁用
    is_active = fields.BooleanField(default=False)  # 表示用户的账户是否已激活
    # 新增：用户拥有的文件
    files = fields.ReverseRelation["File"]
    # 新增：用户拥有的 refresh tokens
    refresh_tokens = fields.ReverseRelation["RefreshToken"]


class RefreshToken(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField('models.User', related_name='refresh_tokens')
    token = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    expires_at = fields.DatetimeField()
    is_revoked = fields.BooleanField(default=False)

    class Meta:
        table = "refresh_tokens"


class FileStatus(str, Enum):
    UPLOADING = "uploading"
    COMPLETED = "completed"
    DOWNLOAD = "download"
    ERROR = "error"


class File(Model):
    id = fields.IntField(pk=True)
    filename = fields.CharField(max_length=255, description="文件名", null=True)
    file_path = fields.CharField(max_length=255, description="文件路径", null=True)
    file_type = fields.CharField(max_length=128, description="MIME类型", null=True)
    key = fields.CharField(max_length=255, description="s3的文件key", null=True)
    upload_id = fields.CharField(max_length=255,description="上传文件的唯一id", null=True)
    file_size = fields.BigIntField(description="文件大小（字节）", null=True)
    total_num = fields.IntField(description="文件分片总数", null=True)
    file_hash = fields.CharField(max_length=255, description="文件哈希值")
    status = fields.CharEnumField(FileStatus, default=FileStatus.UPLOADING, description="标记文件的上传状态")
    upload_progress = fields.IntField(description="记录文件上传的进度（已上传的分片数量）", default=0, null=True)
    last_chunk_uploaded = fields.IntField(description="最后一个上传成功的分片编号", null=True)
    parent = fields.ForeignKeyField('models.Folder', related_name='child_files', null=True, description="父文件夹")
    is_deleted = fields.BooleanField(default=False, description="是否已删除")
    create_time = fields.DatetimeField(auto_now_add=True, description="上传时间")
    user = fields.ForeignKeyField('models.User', related_name='files', description="所属用户")

    class Meta:
        indexes = [("file_hash", "status"), ]  # 为MD5和status字段组合创建索引


class FileChunk(Model):
    id = fields.IntField(pk=True)
    file = fields.ForeignKeyField('models.File', related_name="chunks", description="所属文件")
    chunk_size = fields.IntField(description="文件分片大小（字节）")
    file_hash = fields.CharField(max_length=255, description="文件哈希值")
    chunk_num = fields.IntField(description="当前分片的序号")
    status = fields.CharField(max_length=255, description="标记分片的上传状态", default="pending")
    chunk_path = fields.CharField(max_length=255, description="分片存储路径", null=True)
    create_time = fields.DatetimeField(auto_now_add=True, description="上传时间")

    class Meta:
        indexes = [("file_hash", "chunk_num", "status"), ]  # 为MD5和chunk_num字段组合创建索引


class Folder(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, description="文件夹名称")
    path = fields.CharField(max_length=255, description="文件夹路径", unique=True)
    parent = fields.ForeignKeyField('models.Folder', related_name='subfolders', null=True, description="父文件夹")
    user = fields.ForeignKeyField('models.User', related_name='folders', description="所属用户")
    is_deleted = fields.BooleanField(default=False, description="是否已删除")
    create_time = fields.DatetimeField(auto_now_add=True, description="创建时间")
    update_time = fields.DatetimeField(auto_now=True, description="最后更新时间")
