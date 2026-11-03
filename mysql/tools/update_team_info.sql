-- ============================================
-- 更新用户示例信息
-- ============================================

-- 1. 扩展 users 表，增加班级和自我介绍字段
ALTER TABLE users
    ADD COLUMN major_class VARCHAR(100) DEFAULT NULL COMMENT '专业班级',
    ADD COLUMN bio TEXT DEFAULT NULL COMMENT '自我介绍';

-- 2. 管理员
UPDATE users SET
    real_name = '管理员',
    email = 'admin@example.com',
    phone = '00000000000',
    qq = '0000000000',
    major_class = '示例班级',
    bio = '系统管理员'
WHERE username = 'admin';

-- 3. 用户A
UPDATE users SET
    real_name = '用户A',
    email = 'user1@example.com',
    phone = '00000000000',
    qq = '0000000000',
    major_class = '示例班级',
    bio = '示例用户'
WHERE username = 'testuser';

-- 4. 用户B (新建)
INSERT INTO users (username, password, email, phone, qq, real_name, role_id, major_class, bio, status)
SELECT 'user4', SHA2('123456', 256), 'user4@example.com', '00000000000', '0000000000',
       '用户B', 2, '示例班级', '示例用户', 1
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'user4');
