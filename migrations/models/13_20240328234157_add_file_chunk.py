from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `file` MODIFY COLUMN `key` VARCHAR(255)   COMMENT 's3的文件key';
        ALTER TABLE `file` MODIFY COLUMN `upload_id` VARCHAR(255)   COMMENT '上传文件的唯一id';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `file` MODIFY COLUMN `key` VARCHAR(255) NOT NULL  COMMENT 's3的文件key';
        ALTER TABLE `file` MODIFY COLUMN `upload_id` VARCHAR(255) NOT NULL  COMMENT '上传文件的唯一id';"""
