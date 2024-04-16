from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `user` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `username` VARCHAR(32) NOT NULL  COMMENT '用户名',
    `password_hash` VARCHAR(60) NOT NULL  COMMENT '密码',
    `email` VARCHAR(255)  UNIQUE,
    `avatar` VARCHAR(255)   COMMENT '头像',
    `nick_name` VARCHAR(255) NOT NULL  DEFAULT '昵称',
    `phone_num` VARCHAR(16)   COMMENT '手机号',
    `create_time` DATETIME(6) NOT NULL  COMMENT '注册时间' DEFAULT CURRENT_TIMESTAMP(6),
    `disabled` BOOL NOT NULL  DEFAULT 0,
    `is_active` BOOL NOT NULL  DEFAULT 0
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `folder` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `name` VARCHAR(255) NOT NULL  COMMENT '文件夹名称',
    `path` VARCHAR(255) NOT NULL UNIQUE COMMENT '文件夹路径',
    `is_deleted` BOOL NOT NULL  COMMENT '是否已删除' DEFAULT 0,
    `create_time` DATETIME(6) NOT NULL  COMMENT '创建时间' DEFAULT CURRENT_TIMESTAMP(6),
    `update_time` DATETIME(6) NOT NULL  COMMENT '最后更新时间' DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `parent_id` INT COMMENT '父文件夹',
    `user_id` INT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_folder_folder_c6f195d3` FOREIGN KEY (`parent_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_folder_user_ddb3b5c9` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `file` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `filename` VARCHAR(255)   COMMENT '文件名',
    `file_path` VARCHAR(255)   COMMENT '文件路径',
    `file_type` VARCHAR(128)   COMMENT 'MIME类型',
    `file_size` INT   COMMENT '文件大小（字节）',
    `total_num` INT   COMMENT '文件分片总数',
    `file_hash` VARCHAR(255) NOT NULL  COMMENT '文件哈希值',
    `status` VARCHAR(9) NOT NULL  COMMENT '标记文件的上传状态' DEFAULT 'uploading',
    `upload_progress` INT   COMMENT '记录文件上传的进度（已上传的分片数量）' DEFAULT 0,
    `last_chunk_uploaded` INT   COMMENT '最后一个上传成功的分片编号',
    `is_deleted` BOOL NOT NULL  COMMENT '是否已删除' DEFAULT 0,
    `create_time` DATETIME(6) NOT NULL  COMMENT '上传时间' DEFAULT CURRENT_TIMESTAMP(6),
    `parent_id` INT COMMENT '父文件夹',
    `user_id` INT NOT NULL COMMENT '所属用户',
    CONSTRAINT `fk_file_folder_f3844ee3` FOREIGN KEY (`parent_id`) REFERENCES `folder` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_file_user_476467dc` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
    KEY `idx_file_file_ha_796e7b` (`file_hash`, `status`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `filechunk` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `chunk_size` INT NOT NULL  COMMENT '文件分片大小（字节）',
    `chunk_num` INT NOT NULL  COMMENT '当前分片的序号',
    `file_hash` VARCHAR(255) NOT NULL  COMMENT '文件分片哈希值',
    `status` VARCHAR(255) NOT NULL  COMMENT '标记分片的上传状态' DEFAULT 'pending',
    `chunk_path` VARCHAR(255)   COMMENT '分片存储路径',
    `create_time` DATETIME(6) NOT NULL  COMMENT '上传时间' DEFAULT CURRENT_TIMESTAMP(6),
    `file_id` INT NOT NULL COMMENT '所属文件',
    CONSTRAINT `fk_filechun_file_1969f9f2` FOREIGN KEY (`file_id`) REFERENCES `file` (`id`) ON DELETE CASCADE,
    KEY `idx_filechunk_file_ha_db4e43` (`file_hash`, `chunk_num`, `status`)
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `refresh_tokens` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `token` LONGTEXT NOT NULL,
    `created_at` DATETIME(6) NOT NULL  DEFAULT CURRENT_TIMESTAMP(6),
    `expires_at` DATETIME(6) NOT NULL,
    `is_revoked` BOOL NOT NULL  DEFAULT 0,
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_refresh__user_07a7a7a5` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `aerich` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `version` VARCHAR(255) NOT NULL,
    `app` VARCHAR(100) NOT NULL,
    `content` JSON NOT NULL
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
