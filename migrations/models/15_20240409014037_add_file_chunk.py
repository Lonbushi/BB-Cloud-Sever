from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `file` MODIFY COLUMN `file_size` BIGINT   COMMENT '文件大小（字节）';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `file` MODIFY COLUMN `file_size` INT   COMMENT '文件大小（字节）';"""
