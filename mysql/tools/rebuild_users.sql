-- ============================================
-- 重建 users 表（示例数据）
-- 用法：在 Navicat 中选中 water_quality_db 后执行本脚本
-- ============================================

SET FOREIGN_KEY_CHECKS = 0;

-- 1. 清空 users 表
DELETE FROM users;
ALTER TABLE users AUTO_INCREMENT = 1;

-- 2. 插入示例用户（密码已 SHA-256 哈希）
INSERT INTO `users` (`id`, `username`, `password`, `email`, `phone`, `qq`, `real_name`, `role_id`, `major_class`, `bio`, `create_time`, `last_login_time`, `status`) VALUES
(1, 'admin',   SHA2('admin123', 256),     'admin@example.com',       '00000000000', '0000000000', '管理员', 1, '示例班级', '系统管理员', NOW(), NOW(), 1),
(2, 'testuser',SHA2('test123', 256),      'user1@example.com',       '00000000000', '0000000000', '用户A', 2, '示例班级', '示例用户', NOW(), NOW(), 1),
(3, 'inspector1',SHA2('inspector123', 256),'inspector@example.com',  '00000000000', '0000000000', '检测员', 3, '示例班级', '水质检测相关经验', NOW(), NOW(), 1),
(4, 'user4',   SHA2('123456', 256),       'user4@example.com',       '00000000000', '0000000000', '用户B', 2, '示例班级', '示例用户', NOW(), NOW(), 1);

SET FOREIGN_KEY_CHECKS = 1;

-- 验证
SELECT id, username, real_name, phone, qq, email, major_class, bio FROM users;
