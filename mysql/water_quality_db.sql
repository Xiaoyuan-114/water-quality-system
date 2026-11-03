/*
 Navicat Premium Dump SQL

 Source Server         : localhost_3306
 Source Server Type    : MySQL
 Source Server Version : 90600 (9.6.0)
 Source Host           : localhost:3306
 Source Schema         : water_quality_db

 Target Server Type    : MySQL
 Target Server Version : 90600 (9.6.0)
 File Encoding         : 65001

 Date: 29/05/2026 16:30:00
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 1. 角色表
-- ============================================================
DROP TABLE IF EXISTS `roles`;
CREATE TABLE `roles` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '角色ID',
  `role_name` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '角色名称',
  `description` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '角色描述',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_role_name`(`role_name` ASC) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表' ROW_FORMAT=Dynamic;

INSERT INTO `roles` VALUES (1, 'admin', '系统管理员，拥有全部权限');
INSERT INTO `roles` VALUES (2, 'user', '普通注册用户');
INSERT INTO `roles` VALUES (3, 'inspector', '水质检测员，可批量导入数据');

-- ============================================================
-- 2. 用户表（第三范式：角色信息分离到roles表）
-- ============================================================
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户名',
  `password` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '密码(BCrypt加密)',
  `email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '邮箱',
  `phone` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '手机号',
  `qq` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'QQ号',
  `real_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '真实姓名',
  `role_id` int NOT NULL DEFAULT 2 COMMENT '角色ID',
  `major_class` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '专业班级',
  `bio` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '自我介绍/技能栈',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `last_login_time` datetime DEFAULT NULL COMMENT '最后登录时间',
  `status` tinyint NOT NULL DEFAULT 1 COMMENT '状态:1启用,0禁用',
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_username`(`username` ASC) USING BTREE,
  UNIQUE INDEX `uk_email`(`email` ASC) USING BTREE,
  INDEX `idx_role_id`(`role_id` ASC) USING BTREE,
  CONSTRAINT `fk_users_role` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表' ROW_FORMAT=Dynamic;

-- 示例用户数据（密码已 SHA-256 哈希）
INSERT INTO `users` VALUES (1, 'admin', SHA2('admin123', 256), 'admin@example.com', '00000000000', '0000000000', '管理员', 1, '示例班级', '系统管理员', '2026-05-13 23:08:23', '2026-05-29 16:00:00', 1);
INSERT INTO `users` VALUES (2, 'testuser', SHA2('test123', 256), 'user1@example.com', '00000000000', '0000000000', '用户A', 2, '示例班级', '示例用户', '2026-05-13 23:08:23', '2026-05-29 15:00:00', 1);
INSERT INTO `users` VALUES (3, 'inspector1', SHA2('inspector123', 256), 'inspector@example.com', '00000000000', '0000000000', '检测员', 3, '示例班级', '水质检测相关经验', '2026-05-15 10:00:00', '2026-05-28 09:30:00', 1);
INSERT INTO `users` VALUES (4, 'user4', SHA2('123456', 256), 'user4@example.com', '00000000000', '0000000000', '用户B', 2, '示例班级', '示例用户', '2026-05-20 14:00:00', '2026-05-28 18:00:00', 1);

-- ============================================================
-- 3. 水源信息表（新增 - 丰富业务场景）
-- ============================================================
DROP TABLE IF EXISTS `water_source_info`;
CREATE TABLE `water_source_info` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '水源ID',
  `source_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '水源名称',
  `source_type` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '水源类型(河流/湖泊/地下水/水库/自来水)',
  `province` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '所在省份',
  `city` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '所在城市',
  `latitude` decimal(10,6) DEFAULT NULL COMMENT '纬度',
  `longitude` decimal(10,6) DEFAULT NULL COMMENT '经度',
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '水源描述',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `status` tinyint NOT NULL DEFAULT 1 COMMENT '状态:1启用,0停用',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_source_type`(`source_type` ASC) USING BTREE,
  INDEX `idx_city`(`city` ASC) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='水源信息表' ROW_FORMAT=Dynamic;

INSERT INTO `water_source_info` VALUES (1, '钱塘江杭州段', '河流', '浙江', '杭州', 30.200000, 120.200000, '钱塘江干流杭州市区段采样点', '2026-05-13 23:08:23', 1);
INSERT INTO `water_source_info` VALUES (2, '西湖湖区', '湖泊', '浙江', '杭州', 30.240000, 120.140000, '西湖核心湖区水质监测点', '2026-05-13 23:08:23', 1);
INSERT INTO `water_source_info` VALUES (3, '青山湖水库', '水库', '浙江', '杭州', 30.220000, 119.780000, '临安青山湖水库取水口', '2026-05-13 23:08:23', 1);
INSERT INTO `water_source_info` VALUES (4, '杭州地下水监测1号井', '地下水', '浙江', '杭州', 30.250000, 120.160000, '城区深层地下水监测井', '2026-05-15 10:00:00', 1);
INSERT INTO `water_source_info` VALUES (5, '杭州自来水厂出水口', '自来水', '浙江', '杭州', 30.280000, 120.150000, '市区自来水厂出厂水检测点', '2026-05-15 10:00:00', 1);

-- ============================================================
-- 4. 水质标准表（第三范式：指标和标准值分离合理）
-- ============================================================
DROP TABLE IF EXISTS `water_standard`;
CREATE TABLE `water_standard` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '标准ID',
  `indicator_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '指标名称',
  `min_value` double DEFAULT NULL COMMENT '最小标准值',
  `max_value` double DEFAULT NULL COMMENT '最大标准值',
  `unit` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '单位',
  `standard_level` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '标准等级(饮用水/地表水I类/地表水II类/污水排放)',
  `standard_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '引用标准名称(如GB5749-2022)',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_indicator`(`indicator_name` ASC) USING BTREE,
  INDEX `idx_standard_level`(`standard_level` ASC) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=37 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='水质标准表' ROW_FORMAT=Dynamic;

-- 饮用水标准（GB5749-2022）
INSERT INTO `water_standard` VALUES (1, 'pH', 6.5, 8.5, '-', '饮用水', 'GB5749-2022', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (2, 'hardness', 0, 450, 'mg/L', '饮用水', 'GB5749-2022', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (3, 'solids', 0, 1000, 'ppm', '饮用水', 'GB5749-2022', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (4, 'chloramines', 0, 4, 'ppm', '饮用水', 'GB5749-2022', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (5, 'sulfate', 0, 250, 'mg/L', '饮用水', 'GB5749-2022', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (6, 'conductivity', 0, 1000, 'μS/cm', '饮用水', 'GB5749-2022', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (7, 'organic_carbon', 0, 2, 'ppm', '饮用水', 'GB5749-2022', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (8, 'trihalomethanes', 0, 80, 'μg/L', '饮用水', 'GB5749-2022', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (9, 'turbidity', 0, 5, 'NTU', '饮用水', 'GB5749-2022', '2026-05-13 23:08:23');
-- 地表水I类标准（GB3838-2002）
INSERT INTO `water_standard` VALUES (10, 'pH', 6, 9, '-', '地表水I类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (11, 'hardness', 0, 300, 'mg/L', '地表水I类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (12, 'solids', 0, 500, 'ppm', '地表水I类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (13, 'chloramines', 0, 3, 'ppm', '地表水I类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (14, 'sulfate', 0, 200, 'mg/L', '地表水I类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (15, 'conductivity', 0, 800, 'μS/cm', '地表水I类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (16, 'organic_carbon', 0, 1.5, 'ppm', '地表水I类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (17, 'trihalomethanes', 0, 60, 'μg/L', '地表水I类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (18, 'turbidity', 0, 3, 'NTU', '地表水I类', 'GB3838-2002', '2026-05-13 23:08:23');
-- 地表水II类标准
INSERT INTO `water_standard` VALUES (19, 'pH', 6, 9, '-', '地表水II类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (20, 'hardness', 0, 400, 'mg/L', '地表水II类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (21, 'solids', 0, 800, 'ppm', '地表水II类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (22, 'chloramines', 0, 3.5, 'ppm', '地表水II类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (23, 'sulfate', 0, 230, 'mg/L', '地表水II类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (24, 'conductivity', 0, 900, 'μS/cm', '地表水II类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (25, 'organic_carbon', 0, 1.8, 'ppm', '地表水II类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (26, 'trihalomethanes', 0, 70, 'μg/L', '地表水II类', 'GB3838-2002', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (27, 'turbidity', 0, 4, 'NTU', '地表水II类', 'GB3838-2002', '2026-05-13 23:08:23');
-- 污水排放标准
INSERT INTO `water_standard` VALUES (28, 'pH', 6, 9, '-', '污水排放', 'GB8978-1996', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (29, 'hardness', 0, 600, 'mg/L', '污水排放', 'GB8978-1996', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (30, 'solids', 0, 2000, 'ppm', '污水排放', 'GB8978-1996', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (31, 'chloramines', 0, 6, 'ppm', '污水排放', 'GB8978-1996', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (32, 'sulfate', 0, 400, 'mg/L', '污水排放', 'GB8978-1996', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (33, 'conductivity', 0, 1500, 'μS/cm', '污水排放', 'GB8978-1996', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (34, 'organic_carbon', 0, 5, 'ppm', '污水排放', 'GB8978-1996', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (35, 'trihalomethanes', 0, 120, 'μg/L', '污水排放', 'GB8978-1996', '2026-05-13 23:08:23');
INSERT INTO `water_standard` VALUES (36, 'turbidity', 0, 10, 'NTU', '污水排放', 'GB8978-1996', '2026-05-13 23:08:23');

-- ============================================================
-- 5. 水质检测结果表
-- ============================================================
DROP TABLE IF EXISTS `water_detection`;
CREATE TABLE `water_detection` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '检测记录ID',
  `user_id` int NOT NULL COMMENT '提交用户ID',
  `source_id` int DEFAULT NULL COMMENT '水源ID',
  `ph` double NOT NULL COMMENT 'pH值',
  `hardness` double NOT NULL COMMENT '硬度(mg/L)',
  `solids` double NOT NULL COMMENT '固体含量(ppm)',
  `chloramines` double NOT NULL COMMENT '氯胺(ppm)',
  `sulfate` double NOT NULL COMMENT '硫酸盐(mg/L)',
  `conductivity` double NOT NULL COMMENT '电导率(μS/cm)',
  `organic_carbon` double NOT NULL COMMENT '有机碳(ppm)',
  `trihalomethanes` double NOT NULL COMMENT '三卤甲烷(μg/L)',
  `turbidity` double NOT NULL COMMENT '浊度(NTU)',
  `prediction` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'AI预测结果(Safe/Unsafe)',
  `probability` double NOT NULL COMMENT '预测概率(0-1)',
  `wqi_score` double DEFAULT NULL COMMENT '综合水质指数(WQI)',
  `water_grade` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '水质等级',
  `standard_level` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '参考标准等级',
  `detect_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '检测时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_user_id`(`user_id` ASC) USING BTREE,
  INDEX `idx_detect_time`(`detect_time` ASC) USING BTREE,
  INDEX `idx_probability`(`probability` ASC) USING BTREE,
  INDEX `idx_source_id`(`source_id` ASC) USING BTREE,
  INDEX `idx_prediction`(`prediction` ASC) USING BTREE,
  CONSTRAINT `fk_detection_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_detection_source` FOREIGN KEY (`source_id`) REFERENCES `water_source_info` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='水质检测结果表(AI预测)' ROW_FORMAT=Dynamic;

INSERT INTO `water_detection` VALUES (7, 2, 1, 7.2, 150.3, 320.5, 2.1, 180.2, 450, 1.2, 25, 2.3, 'Safe', 0.92, 85.5, 'Good', '饮用水', '2026-05-13 23:13:56');
INSERT INTO `water_detection` VALUES (8, 2, 2, 6.8, 180.5, 480.2, 3.5, 210.4, 620, 2.5, 45, 3.8, 'Safe', 0.85, 72.3, 'Fair', '地表水I类', '2026-05-13 23:13:56');
INSERT INTO `water_detection` VALUES (9, 2, 4, 8.9, 220, 850, 5.2, 280.6, 890, 3.8, 95, 6.2, 'Unsafe', 0.28, 35.1, 'Poor', '污水排放', '2026-05-13 23:13:56');
INSERT INTO `water_detection` VALUES (18, 2, 1, 8, 400, 1200, 6, 350, 1100, 5, 150, 10, 'Unsafe', 0.20, 22.0, 'Dangerous', '污水排放', '2026-05-13 23:28:03');
INSERT INTO `water_detection` VALUES (19, 3, 3, 8.5, 300, 900, 5.5, 300, 950, 4.5, 120, 8, 'Unsafe', 0.25, 30.8, 'Poor', '污水排放', '2026-05-14 00:33:50');
INSERT INTO `water_detection` VALUES (20, 3, 5, 7, 200, 500, 2, 150, 600, 2, 60, 4, 'Safe', 0.50, 65.2, 'Fair', '地表水II类', '2026-05-14 00:33:50');
INSERT INTO `water_detection` VALUES (21, 4, 1, 7.2, 180, 400, 2.5, 200, 550, 1.8, 30, 3, 'Safe', 0.90, 88.0, 'Excellent', '饮用水', '2025-05-01 10:00:00');

-- ============================================================
-- 6. 警告日志表
-- ============================================================
DROP TABLE IF EXISTS `warning_log`;
CREATE TABLE `warning_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `detection_id` int NOT NULL COMMENT '关联检测记录ID',
  `warning_level` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '警告级别(高/中/低)',
  `warning_message` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '警告信息',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `is_resolved` tinyint NOT NULL DEFAULT 0 COMMENT '是否已解决:0未解决,1已解决',
  `handle_time` datetime DEFAULT NULL COMMENT '处理时间',
  `handler_id` int DEFAULT NULL COMMENT '处理人ID',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_detection_id`(`detection_id` ASC) USING BTREE,
  INDEX `idx_warning_level`(`warning_level` ASC) USING BTREE,
  INDEX `idx_is_resolved`(`is_resolved` ASC) USING BTREE,
  CONSTRAINT `fk_warning_detection` FOREIGN KEY (`detection_id`) REFERENCES `water_detection` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_warning_handler` FOREIGN KEY (`handler_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='水质警告日志表' ROW_FORMAT=Dynamic;

INSERT INTO `warning_log` VALUES (13, 18, '高', '水质危险，预测概率仅0.2，结果为Unsafe', '2026-05-13 23:28:03', 1, '2026-05-13 23:28:03', 1);
INSERT INTO `warning_log` VALUES (14, 19, '高', '水质危险，预测概率仅0.25，结果为Unsafe', '2026-05-14 00:33:50', 0, NULL, NULL);
INSERT INTO `warning_log` VALUES (15, 20, '中', '水质警告，概率0.5，接近临界值', '2026-05-14 00:33:50', 0, NULL, NULL);

-- ============================================================
-- 7. 检测操作历史表（增强版）
-- ============================================================
DROP TABLE IF EXISTS `detection_history`;
CREATE TABLE `detection_history` (
  `id` int NOT NULL AUTO_INCREMENT,
  `detection_id` int NOT NULL COMMENT '关联检测记录ID',
  `operation_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '操作类型(INSERT/UPDATE/DELETE)',
  `operator_id` int DEFAULT NULL COMMENT '操作者ID',
  `operation_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
  `old_data` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '变更前数据(JSON)',
  `new_data` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '变更后数据(JSON)',
  `remark` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '备注',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_detection_id`(`detection_id` ASC) USING BTREE,
  INDEX `idx_operator_id`(`operator_id` ASC) USING BTREE,
  INDEX `idx_operation_time`(`operation_time` ASC) USING BTREE,
  CONSTRAINT `fk_history_detection` FOREIGN KEY (`detection_id`) REFERENCES `water_detection` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_history_operator` FOREIGN KEY (`operator_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='检测操作历史表' ROW_FORMAT=Dynamic;

-- ============================================================
-- 8. 系统操作日志表
-- ============================================================
DROP TABLE IF EXISTS `system_log`;
CREATE TABLE `system_log` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL COMMENT '操作用户ID',
  `operation` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '操作描述',
  `operation_type` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'SYSTEM' COMMENT '操作类别(LOGIN/DETECTION/WARNING/ADMIN)',
  `operation_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `ip_address` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'IP地址',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_user_id`(`user_id` ASC) USING BTREE,
  INDEX `idx_operation_time`(`operation_time` ASC) USING BTREE,
  INDEX `idx_operation_type`(`operation_type` ASC) USING BTREE,
  CONSTRAINT `fk_syslog_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统操作日志表' ROW_FORMAT=Dynamic;

INSERT INTO `system_log` VALUES (1, 1, '自动处理高警告 ID=13，检测记录ID=18', 'WARNING', '2026-05-13 23:22:26', '127.0.0.1');
INSERT INTO `system_log` VALUES (2, 1, '用户admin登录系统', 'LOGIN', '2026-05-29 16:00:00', '127.0.0.1');

-- ============================================================
-- 9. AI模型评估信息表（丰富字段）
-- ============================================================
DROP TABLE IF EXISTS `ai_model_info`;
CREATE TABLE `ai_model_info` (
  `id` int NOT NULL AUTO_INCREMENT,
  `model_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '模型名称',
  `model_type` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '模型类型(traditional/deep_learning/ensemble/anomaly_detection)',
  `accuracy` double DEFAULT NULL COMMENT '准确率',
  `f1_score` double DEFAULT NULL COMMENT 'F1分数',
  `auc` double DEFAULT NULL COMMENT 'AUC值',
  `precision_score` double DEFAULT NULL COMMENT '精确率',
  `recall_score` double DEFAULT NULL COMMENT '召回率',
  `cv_f1_mean` double DEFAULT NULL COMMENT '交叉验证F1均值',
  `best_threshold` double DEFAULT NULL COMMENT '最佳阈值',
  `is_production` tinyint NOT NULL DEFAULT 0 COMMENT '是否生产环境模型:1是,0否',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_model_type`(`model_type` ASC) USING BTREE
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI模型评估信息表' ROW_FORMAT=Dynamic;

-- 指标来源：WaterQualityAI/model_train.py 的 5折x3次重复交叉验证（全量3276条），
-- 每折在自身训练部分内部完成概率标定与定阈值，测试集不参与选择。
-- 与 WaterQualityAI/model_evaluation.csv 逐行一致；重训模型后需同步这里。
INSERT INTO `ai_model_info` VALUES (1, '决策树', 'traditional', 0.6195, 0.4128, 0.5962, 0.5268, 0.3498, 0.4128, 0.392, 0, '2026-11-03 16:50:32');
INSERT INTO `ai_model_info` VALUES (2, '随机森林', 'traditional', 0.6584, 0.5390, 0.6868, 0.5726, 0.5133, 0.5390, 0.428, 0, '2026-11-03 16:50:32');
INSERT INTO `ai_model_info` VALUES (3, 'SVM', 'traditional', 0.6607, 0.5540, 0.6956, 0.5693, 0.5412, 0.5540, 0.427, 0, '2026-11-03 16:50:32');
INSERT INTO `ai_model_info` VALUES (4, '梯度提升树', 'traditional', 0.6257, 0.4899, 0.6478, 0.5267, 0.4637, 0.4899, 0.403, 0, '2026-11-03 16:50:32');
INSERT INTO `ai_model_info` VALUES (5, 'XGBoost', 'traditional', 0.6348, 0.5111, 0.6639, 0.5405, 0.4917, 0.5111, 0.416, 0, '2026-11-03 16:50:32');
INSERT INTO `ai_model_info` VALUES (6, 'LightGBM', 'traditional', 0.6427, 0.5123, 0.6691, 0.5496, 0.4828, 0.5123, 0.425, 0, '2026-11-03 16:50:32');
INSERT INTO `ai_model_info` VALUES (7, '集成学习Voting', 'ensemble', 0.6641, 0.5573, 0.7025, 0.5766, 0.5433, 0.5573, 0.440, 1, '2026-11-03 16:50:32');
-- LSTM 和 IsolationForest 模型已移除：指标未经真实评估，不应出现在仪表盘中
--
-- 已经建过库的环境不要重跑整个脚本，执行下面这组语句同步模型表即可：
--   UPDATE `ai_model_info` SET accuracy=0.6195, f1_score=0.4128, auc=0.5962, precision_score=0.5268, recall_score=0.3498, cv_f1_mean=0.4128, best_threshold=0.392, create_time='2026-11-03 16:50:32' WHERE id=1;
--   UPDATE `ai_model_info` SET accuracy=0.6584, f1_score=0.5390, auc=0.6868, precision_score=0.5726, recall_score=0.5133, cv_f1_mean=0.5390, best_threshold=0.428, create_time='2026-11-03 16:50:32' WHERE id=2;
--   UPDATE `ai_model_info` SET accuracy=0.6607, f1_score=0.5540, auc=0.6956, precision_score=0.5693, recall_score=0.5412, cv_f1_mean=0.5540, best_threshold=0.427, create_time='2026-11-03 16:50:32' WHERE id=3;
--   UPDATE `ai_model_info` SET accuracy=0.6257, f1_score=0.4899, auc=0.6478, precision_score=0.5267, recall_score=0.4637, cv_f1_mean=0.4899, best_threshold=0.403, create_time='2026-11-03 16:50:32' WHERE id=4;
--   UPDATE `ai_model_info` SET accuracy=0.6348, f1_score=0.5111, auc=0.6639, precision_score=0.5405, recall_score=0.4917, cv_f1_mean=0.5111, best_threshold=0.416, create_time='2026-11-03 16:50:32' WHERE id=5;
--   UPDATE `ai_model_info` SET accuracy=0.6427, f1_score=0.5123, auc=0.6691, precision_score=0.5496, recall_score=0.4828, cv_f1_mean=0.5123, best_threshold=0.425, create_time='2026-11-03 16:50:32' WHERE id=6;
--   UPDATE `ai_model_info` SET accuracy=0.6641, f1_score=0.5573, auc=0.7025, precision_score=0.5766, recall_score=0.5433, cv_f1_mean=0.5573, best_threshold=0.440, is_production=1, create_time='2026-11-03 16:50:32' WHERE id=7;

-- ============================================================
-- 10. 系统公告表
-- ============================================================
DROP TABLE IF EXISTS `announcement`;
CREATE TABLE `announcement` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `summary` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '摘要',
  `category` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'system' COMMENT '公告分类',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `publisher_id` int NOT NULL COMMENT '发布人ID',
  `is_top` tinyint NOT NULL DEFAULT 0 COMMENT '是否置顶',
  `view_count` int NOT NULL DEFAULT 0 COMMENT '浏览次数',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_publisher`(`publisher_id` ASC) USING BTREE,
  INDEX `idx_create_time`(`create_time` ASC) USING BTREE,
  INDEX `idx_category`(`category` ASC) USING BTREE,
  CONSTRAINT `fk_announcement_user` FOREIGN KEY (`publisher_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统公告表' ROW_FORMAT=Dynamic;

INSERT INTO `announcement` VALUES (1, '水质检测系统V2.0上线通知', '智能水质检测系统V2.0版本正式上线，新增7种机器学习模型对比分析、水源管理等功能，欢迎使用。', '系统重大更新', 'system', '2026-05-13 23:08:23', 1, 1, 128);
INSERT INTO `announcement` VALUES (2, 'AI模型升级说明', '生产模型已切换为集成学习Voting（SVM+随机森林 soft voting，sigmoid 概率标定）。5折x3次重复交叉验证：准确率0.664、F1 0.557、AUC 0.703；旧线上模型同口径为0.627、0.538、0.672。', '模型升级', 'model', '2026-11-03 16:50:32', 1, 0, 56);
INSERT INTO `announcement` VALUES (3, '新增水质标准参考', '系统已更新至最新GB5749-2022《生活饮用水卫生标准》及GB3838-2002《地表水环境质量标准》。', '数据更新', 'standard', '2026-05-15 10:00:00', 1, 0, 34);
INSERT INTO `announcement` VALUES (4, '水质检测操作指南', '本文档详细介绍如何使用系统的各项功能：水质检测、历史查询、数据分析、警告处理等。', '使用帮助', 'guide', '2026-05-15 10:00:00', 1, 0, 89);

-- ============================================================
-- 11. 用户反馈表
-- ============================================================
DROP TABLE IF EXISTS `feedback`;
CREATE TABLE `feedback` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL COMMENT '反馈用户ID',
  `title` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '反馈标题',
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '反馈内容',
  `feedback_type` varchar(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'suggestion' COMMENT '类型(建议/问题/投诉)',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `status` tinyint NOT NULL DEFAULT 0 COMMENT '处理状态:0未处理,1已读,2已回复',
  `reply` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT '回复内容',
  `reply_time` datetime DEFAULT NULL COMMENT '回复时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_user_id`(`user_id` ASC) USING BTREE,
  INDEX `idx_status`(`status` ASC) USING BTREE,
  CONSTRAINT `fk_feedback_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户反馈表' ROW_FORMAT=Dynamic;

INSERT INTO `feedback` VALUES (1, 2, '建议增加批量导入功能', '希望系统能支持CSV文件批量导入检测数据，方便一次性分析大量水样。', 'suggestion', '2026-05-14 10:00:00', 2, '感谢您的建议！批量导入功能已列入开发计划，预计下个版本支持。', '2026-05-15 09:00:00');
INSERT INTO `feedback` VALUES (2, 4, '检测结果展示建议', '检测结果页面能否同时显示多个模型的预测对比？这样更有参考价值。', 'suggestion', '2026-05-20 14:30:00', 1, NULL, NULL);

-- ============================================================
-- 12. 检测标准变更日志表（新增）
-- ============================================================
DROP TABLE IF EXISTS `standard_change_log`;
CREATE TABLE `standard_change_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `standard_id` int NOT NULL COMMENT '标准ID',
  `field_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '变更字段',
  `old_value` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '旧值',
  `new_value` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '新值',
  `change_reason` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '变更原因',
  `operator_id` int DEFAULT NULL COMMENT '操作人ID',
  `change_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_standard_id`(`standard_id` ASC) USING BTREE,
  INDEX `idx_change_time`(`change_time` ASC) USING BTREE,
  CONSTRAINT `fk_changelog_standard` FOREIGN KEY (`standard_id`) REFERENCES `water_standard` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_changelog_operator` FOREIGN KEY (`operator_id`) REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='检测标准变更日志表' ROW_FORMAT=Dynamic;

-- ============================================================
-- 视图1: 安全水质汇总视图
-- ============================================================
DROP VIEW IF EXISTS `v_safe_water`;
CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `v_safe_water` AS
SELECT
    d.id,
    u.username,
    ws.source_name,
    ws.source_type,
    d.ph,
    d.turbidity,
    d.prediction,
    d.probability,
    d.wqi_score,
    d.water_grade,
    d.detect_time
FROM water_detection d
JOIN users u ON d.user_id = u.id
LEFT JOIN water_source_info ws ON d.source_id = ws.id
WHERE d.probability >= 0.7;

-- ============================================================
-- 视图2: 检测统计汇总视图（按日/月）
-- ============================================================
DROP VIEW IF EXISTS `v_detection_summary`;
CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `v_detection_summary` AS
SELECT
    DATE(detect_time) AS detect_date,
    YEAR(detect_time) AS detect_year,
    MONTH(detect_time) AS detect_month,
    COUNT(*) AS total_detections,
    ROUND(AVG(ph), 2) AS avg_ph,
    ROUND(AVG(turbidity), 2) AS avg_turbidity,
    ROUND(AVG(probability), 4) AS avg_probability,
    SUM(CASE WHEN prediction = 'Safe' THEN 1 ELSE 0 END) AS safe_count,
    SUM(CASE WHEN prediction = 'Unsafe' THEN 1 ELSE 0 END) AS unsafe_count,
    ROUND(SUM(CASE WHEN prediction = 'Safe' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS safe_rate
FROM water_detection
GROUP BY DATE(detect_time), YEAR(detect_time), MONTH(detect_time);

-- ============================================================
-- 视图3: 高风险水源汇总视图
-- ============================================================
DROP VIEW IF EXISTS `v_high_risk_waters`;
CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `v_high_risk_waters` AS
SELECT
    ws.id AS source_id,
    ws.source_name,
    ws.source_type,
    ws.city,
    COUNT(d.id) AS unsafe_count,
    ROUND(AVG(d.probability), 4) AS avg_risk_probability,
    MIN(d.detect_time) AS first_unsafe_time,
    MAX(d.detect_time) AS last_unsafe_time
FROM water_source_info ws
JOIN water_detection d ON ws.id = d.source_id
WHERE d.prediction = 'Unsafe'
GROUP BY ws.id, ws.source_name, ws.source_type, ws.city
HAVING unsafe_count >= 1;

-- ============================================================
-- 视图4: 用户检测统计视图
-- ============================================================
DROP VIEW IF EXISTS `v_user_detection_stats`;
CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `v_user_detection_stats` AS
SELECT
    u.id AS user_id,
    u.username,
    u.real_name,
    r.role_name,
    COUNT(d.id) AS total_detections,
    SUM(CASE WHEN d.prediction = 'Safe' THEN 1 ELSE 0 END) AS safe_count,
    SUM(CASE WHEN d.prediction = 'Unsafe' THEN 1 ELSE 0 END) AS unsafe_count,
    ROUND(AVG(d.probability), 4) AS avg_probability,
    MAX(d.detect_time) AS last_detection_time
FROM users u
JOIN roles r ON u.role_id = r.id
LEFT JOIN water_detection d ON u.id = d.user_id
WHERE u.status = 1
GROUP BY u.id, u.username, u.real_name, r.role_name;

-- ============================================================
-- 存储函数1: 水质等级分类
-- ============================================================
DROP FUNCTION IF EXISTS `classify_water_quality`;
DELIMITER ;;
CREATE FUNCTION `classify_water_quality`(p_probability DOUBLE)
 RETURNS varchar(20) CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci
  DETERMINISTIC
  COMMENT '根据预测概率返回水质等级'
BEGIN
    DECLARE grade VARCHAR(20);
    IF p_probability >= 0.9 THEN
        SET grade = 'Excellent';
    ELSEIF p_probability >= 0.8 THEN
        SET grade = 'Good';
    ELSEIF p_probability >= 0.6 THEN
        SET grade = 'Fair';
    ELSEIF p_probability >= 0.3 THEN
        SET grade = 'Poor';
    ELSE
        SET grade = 'Dangerous';
    END IF;
    RETURN grade;
END
;;
DELIMITER ;

-- ============================================================
-- 存储函数2: 计算综合水质指数(WQI)
-- ============================================================
DROP FUNCTION IF EXISTS `calculate_wqi`;
DELIMITER ;;
CREATE FUNCTION `calculate_wqi`(
    p_ph DOUBLE, p_hardness DOUBLE, p_solids DOUBLE,
    p_chloramines DOUBLE, p_sulfate DOUBLE, p_conductivity DOUBLE,
    p_organic_carbon DOUBLE, p_trihalomethanes DOUBLE, p_turbidity DOUBLE
)
 RETURNS double
  DETERMINISTIC
  COMMENT '计算综合水质指数(WQI)，满分100'
BEGIN
    DECLARE wqi DOUBLE;
    DECLARE ph_score DOUBLE;
    DECLARE hardness_score DOUBLE;
    DECLARE solids_score DOUBLE;
    DECLARE chloramines_score DOUBLE;
    DECLARE sulfate_score DOUBLE;
    DECLARE conductivity_score DOUBLE;
    DECLARE organic_score DOUBLE;
    DECLARE thm_score DOUBLE;
    DECLARE turbidity_score DOUBLE;

    -- pH评分 (理想值7.0)
    SET ph_score = 100 - ABS(p_ph - 7.0) * 15;
    IF ph_score < 0 THEN SET ph_score = 0; END IF;

    SET hardness_score = 100 - (p_hardness / 500) * 100;
    IF hardness_score < 0 THEN SET hardness_score = 0; END IF;

    SET solids_score = 100 - (p_solids / 1500) * 100;
    IF solids_score < 0 THEN SET solids_score = 0; END IF;

    SET chloramines_score = 100 - (p_chloramines / 5) * 100;
    IF chloramines_score < 0 THEN SET chloramines_score = 0; END IF;

    SET sulfate_score = 100 - (p_sulfate / 400) * 100;
    IF sulfate_score < 0 THEN SET sulfate_score = 0; END IF;

    SET conductivity_score = 100 - (p_conductivity / 1500) * 100;
    IF conductivity_score < 0 THEN SET conductivity_score = 0; END IF;

    SET organic_score = 100 - (p_organic_carbon / 10) * 100;
    IF organic_score < 0 THEN SET organic_score = 0; END IF;

    SET thm_score = 100 - (p_trihalomethanes / 120) * 100;
    IF thm_score < 0 THEN SET thm_score = 0; END IF;

    SET turbidity_score = 100 - (p_turbidity / 10) * 100;
    IF turbidity_score < 0 THEN SET turbidity_score = 0; END IF;

    SET wqi = (ph_score * 0.12 + hardness_score * 0.10 + solids_score * 0.10 +
               chloramines_score * 0.12 + sulfate_score * 0.10 + conductivity_score * 0.10 +
               organic_score * 0.12 + thm_score * 0.12 + turbidity_score * 0.12);

    RETURN ROUND(wqi, 2);
END
;;
DELIMITER ;

-- ============================================================
-- 存储过程1: 生成每日水质报告
-- ============================================================
DROP PROCEDURE IF EXISTS `generate_daily_report`;
DELIMITER ;;
CREATE PROCEDURE `generate_daily_report`(IN report_date DATE)
  COMMENT '生成指定日期的水质检测日报'
BEGIN
    SELECT
        report_date AS '报告日期',
        COUNT(*) AS '总检测数',
        ROUND(AVG(ph), 2) AS '平均pH',
        ROUND(AVG(turbidity), 2) AS '平均浊度NTU',
        ROUND(AVG(probability), 4) AS '平均安全概率',
        SUM(CASE WHEN prediction = 'Safe' THEN 1 ELSE 0 END) AS '安全数量',
        SUM(CASE WHEN prediction = 'Unsafe' THEN 1 ELSE 0 END) AS '不安全数量',
        ROUND(SUM(CASE WHEN prediction = 'Safe' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS '安全率',
        ROUND(AVG(wqi_score), 2) AS '平均WQI指数'
    FROM water_detection
    WHERE DATE(detect_time) = report_date;
END
;;
DELIMITER ;

-- ============================================================
-- 存储过程2: 处理高风险警告（带游标）
-- ============================================================
DROP PROCEDURE IF EXISTS `process_high_risk_warnings`;
DELIMITER ;;
CREATE PROCEDURE `process_high_risk_warnings`()
  COMMENT '使用游标遍历并处理所有未解决的高级别警告'
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE v_warning_id INT;
    DECLARE v_detection_id INT;
    DECLARE v_warning_level VARCHAR(20);
    DECLARE v_message VARCHAR(200);

    DECLARE cur CURSOR FOR
        SELECT id, detection_id, warning_level, warning_message
        FROM warning_log
        WHERE is_resolved = 0 AND warning_level = '高'
        ORDER BY create_time ASC;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    OPEN cur;

    read_loop: LOOP
        FETCH cur INTO v_warning_id, v_detection_id, v_warning_level, v_message;
        IF done THEN
            LEAVE read_loop;
        END IF;

        UPDATE warning_log
        SET is_resolved = 1, handle_time = NOW(), handler_id = 1
        WHERE id = v_warning_id;

        INSERT INTO system_log (user_id, operation, operation_type, ip_address)
        VALUES (1, CONCAT('自动处理高警告 ID=', v_warning_id, '，检测记录ID=', v_detection_id), 'WARNING', '127.0.0.1');

    END LOOP;

    CLOSE cur;
END
;;
DELIMITER ;

-- ============================================================
-- 存储过程3: 月度水质分析报告（带游标遍历水源）
-- ============================================================
DROP PROCEDURE IF EXISTS `sp_monthly_report`;
DELIMITER ;;
CREATE PROCEDURE `sp_monthly_report`(IN p_year INT, IN p_month INT)
  COMMENT '生成指定月份的详细水质分析报告，使用游标遍历各水源'
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE v_source_id INT;
    DECLARE v_source_name VARCHAR(100);
    DECLARE v_source_type VARCHAR(30);
    DECLARE v_total INT;
    DECLARE v_safe INT;
    DECLARE v_unsafe INT;
    DECLARE v_avg_prob DOUBLE;

    DECLARE source_cursor CURSOR FOR
        SELECT id, source_name, source_type FROM water_source_info WHERE status = 1;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    -- 总览统计
    SELECT
        CONCAT(p_year, '-', LPAD(p_month, 2, '0')) AS '报告月份',
        COUNT(*) AS '总检测数',
        ROUND(AVG(probability), 4) AS '平均安全概率',
        ROUND(AVG(wqi_score), 2) AS '平均WQI指数',
        SUM(CASE WHEN prediction = 'Safe' THEN 1 ELSE 0 END) AS '安全水样数',
        SUM(CASE WHEN prediction = 'Unsafe' THEN 1 ELSE 0 END) AS '不安全水样数'
    FROM water_detection
    WHERE YEAR(detect_time) = p_year AND MONTH(detect_time) = p_month;

    -- 按水源类型统计
    SELECT
        ws.source_type AS '水源类型',
        COUNT(*) AS '检测次数',
        ROUND(AVG(d.probability), 4) AS '平均安全概率',
        SUM(CASE WHEN d.prediction = 'Unsafe' THEN 1 ELSE 0 END) AS '不安全次数'
    FROM water_detection d
    JOIN water_source_info ws ON d.source_id = ws.id
    WHERE YEAR(d.detect_time) = p_year AND MONTH(d.detect_time) = p_month
    GROUP BY ws.source_type;

    -- 游标遍历各水源详情
    OPEN source_cursor;
    source_loop: LOOP
        FETCH source_cursor INTO v_source_id, v_source_name, v_source_type;
        IF done THEN LEAVE source_loop; END IF;

        SELECT COUNT(*), SUM(CASE WHEN prediction = 'Safe' THEN 1 ELSE 0 END),
               SUM(CASE WHEN prediction = 'Unsafe' THEN 1 ELSE 0 END), ROUND(AVG(probability), 4)
        INTO v_total, v_safe, v_unsafe, v_avg_prob
        FROM water_detection
        WHERE source_id = v_source_id
          AND YEAR(detect_time) = p_year AND MONTH(detect_time) = p_month;

        IF v_total > 0 THEN
            SELECT CONCAT(v_source_name, ' (', v_source_type, ')') AS '水源',
                   v_total AS '检测数', v_safe AS '安全', v_unsafe AS '不安全', v_avg_prob AS '均概率';
        END IF;
    END LOOP;

    CLOSE source_cursor;
END
;;
DELIMITER ;

-- ============================================================
-- 存储过程4: 用户活跃度分析（带游标）
-- ============================================================
DROP PROCEDURE IF EXISTS `sp_user_activity_analysis`;
DELIMITER ;;
CREATE PROCEDURE `sp_user_activity_analysis`(IN p_days INT)
  COMMENT '分析最近N天内的用户活跃度'
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE v_user_id INT;
    DECLARE v_username VARCHAR(50);
    DECLARE v_real_name VARCHAR(50);
    DECLARE v_detection_count INT;
    DECLARE v_last_active DATETIME;
    DECLARE v_role VARCHAR(30);

    DECLARE user_cursor CURSOR FOR
        SELECT u.id, u.username, u.real_name, r.role_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.status = 1;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    SELECT CONCAT('=== 最近 ', p_days, ' 天用户活跃度分析 ===') AS '报告标题';
    SELECT '----------------------------------------' AS '';

    OPEN user_cursor;
    user_loop: LOOP
        FETCH user_cursor INTO v_user_id, v_username, v_real_name, v_role;
        IF done THEN LEAVE user_loop; END IF;

        SELECT COUNT(*), MAX(detect_time)
        INTO v_detection_count, v_last_active
        FROM water_detection
        WHERE user_id = v_user_id
          AND detect_time >= DATE_SUB(NOW(), INTERVAL p_days DAY);

        SELECT CONCAT('用户: ', COALESCE(v_real_name, v_username),
                      ' (', v_role, ')',
                      ' - 检测次数: ', v_detection_count,
                      ' - 最后活跃: ', COALESCE(DATE_FORMAT(v_last_active, '%Y-%m-%d %H:%i'), '无记录')) AS '用户活跃详情';
    END LOOP;

    CLOSE user_cursor;
END
;;
DELIMITER ;

-- ============================================================
-- 触发器1: 检测记录插入后自动生成警告
-- ============================================================
DROP TRIGGER IF EXISTS `trg_insert_warning`;
DELIMITER ;;
CREATE TRIGGER `trg_insert_warning`
  AFTER INSERT ON `water_detection` FOR EACH ROW
BEGIN
    DECLARE warn_level VARCHAR(20);
    DECLARE warn_msg VARCHAR(200);

    IF NEW.probability < 0.3 THEN
        SET warn_level = '高';
        SET warn_msg = CONCAT('水质危险，预测概率仅', NEW.probability, '，结果为', NEW.prediction);
        INSERT INTO `warning_log` (`detection_id`, `warning_level`, `warning_message`)
        VALUES (NEW.id, warn_level, warn_msg);

    ELSEIF NEW.probability < 0.6 THEN
        SET warn_level = '中';
        SET warn_msg = CONCAT('水质警告，概率', NEW.probability, '，需关注');
        INSERT INTO `warning_log` (`detection_id`, `warning_level`, `warning_message`)
        VALUES (NEW.id, warn_level, warn_msg);

    ELSEIF NEW.probability < 0.8 THEN
        SET warn_level = '低';
        SET warn_msg = CONCAT('水质提醒，概率', NEW.probability, '，建议复查');
        INSERT INTO `warning_log` (`detection_id`, `warning_level`, `warning_message`)
        VALUES (NEW.id, warn_level, warn_msg);
    END IF;
END
;;
DELIMITER ;

-- ============================================================
-- 触发器2: 检测记录变更自动记录历史
-- ============================================================
DROP TRIGGER IF EXISTS `trg_detection_update_history`;
DELIMITER ;;
CREATE TRIGGER `trg_detection_update_history`
  AFTER UPDATE ON `water_detection` FOR EACH ROW
BEGIN
    INSERT INTO `detection_history` (
        `detection_id`, `operation_type`, `operator_id`, `operation_time`,
        `old_data`, `new_data`, `remark`
    ) VALUES (
        NEW.id, 'UPDATE', NEW.user_id, NOW(),
        CONCAT('{"prediction":"', OLD.prediction, '","probability":', OLD.probability,
               ',"wqi_score":', IFNULL(OLD.wqi_score, 'null'), '}'),
        CONCAT('{"prediction":"', NEW.prediction, '","probability":', NEW.probability,
               ',"wqi_score":', IFNULL(NEW.wqi_score, 'null'), '}'),
        '检测记录更新'
    );
END
;;
DELIMITER ;

-- ============================================================
-- 触发器3: 检测标准变更记录日志
-- ============================================================
DROP TRIGGER IF EXISTS `trg_standard_update_log`;
DELIMITER ;;
CREATE TRIGGER `trg_standard_update_log`
  AFTER UPDATE ON `water_standard` FOR EACH ROW
BEGIN
    IF OLD.min_value <> NEW.min_value OR OLD.max_value <> NEW.max_value THEN
        INSERT INTO `standard_change_log` (
            `standard_id`, `field_name`, `old_value`, `new_value`,
            `change_reason`, `operator_id`, `change_time`
        ) VALUES (
            NEW.id, 'value_range',
            CONCAT(IFNULL(OLD.min_value, 'NULL'), '-', IFNULL(OLD.max_value, 'NULL')),
            CONCAT(IFNULL(NEW.min_value, 'NULL'), '-', IFNULL(NEW.max_value, 'NULL')),
            '标准值更新', NULL, NOW()
        );
    END IF;
END
;;
DELIMITER ;

-- ============================================================
-- 触发器4: 告警解决后记录日志
-- ============================================================
DROP TRIGGER IF EXISTS `trg_warning_resolved_log`;
DELIMITER ;;
CREATE TRIGGER `trg_warning_resolved_log`
  AFTER UPDATE ON `warning_log` FOR EACH ROW
BEGIN
    IF OLD.is_resolved = 0 AND NEW.is_resolved = 1 THEN
        INSERT INTO `system_log` (`user_id`, `operation`, `operation_type`, `ip_address`)
        VALUES (
            IFNULL(NEW.handler_id, 1),
            CONCAT('警告已解决 ID=', NEW.id, '，原级别:', NEW.warning_level),
            'WARNING', '127.0.0.1'
        );
    END IF;
END
;;
DELIMITER ;

SET FOREIGN_KEY_CHECKS = 1;