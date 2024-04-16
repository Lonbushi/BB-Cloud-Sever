from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `file` ADD `upload_id` VARCHAR(255) NOT NULL  COMMENT '上传文件的唯一id';
        ALTER TABLE `file` ADD `key` VARCHAR(255) NOT NULL  COMMENT 's3的文件key';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `file` DROP COLUMN `upload_id`;
        ALTER TABLE `file` DROP COLUMN `key`;"""
