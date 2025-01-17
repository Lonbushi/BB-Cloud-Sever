from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `filechunk` ADD `file_hash` VARCHAR(255) NOT NULL  COMMENT '文件哈希值';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `filechunk` DROP COLUMN `file_hash`;"""
