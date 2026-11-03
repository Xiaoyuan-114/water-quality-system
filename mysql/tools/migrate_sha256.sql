-- ====================================================
-- 密码 SHA-256 迁移脚本
-- 将 users 表中所有明文密码替换为 SHA-256 哈希值
--
-- 用法：在 Navicat 中选中 water_quality_db，执行本脚本。
--       然后重新部署 WaterQualitySystem 的 WAR 包。
--       此脚本只需执行一次。
-- ====================================================

UPDATE users SET password = SHA2('admin123', 256)     WHERE username = 'admin';
UPDATE users SET password = SHA2('test123', 256)      WHERE username = 'testuser';
UPDATE users SET password = SHA2('inspector123', 256) WHERE username = 'inspector1';
UPDATE users SET password = SHA2('123456', 256)       WHERE username = 'chenzhh';

-- 验证密码列已哈希（应显示 64 位十六进制字符串）
SELECT id, username, password FROM users;
