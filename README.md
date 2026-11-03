# 水质AI检测系统 · Water Quality AI Detection System

基于机器学习的饮用水水质安全预测系统，融合 **Jakarta EE Web 应用** 与 **Python FastAPI AI 微服务**，支持用户管理、水质预测、数据可视化、数据库备份恢复等完整功能。

> 🎓 人工智能引论 + 数据库原理与技术实习 课程设计

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   Browser (用户端)                    │
├─────────────────────────────────────────────────────┤
│  Jakarta EE Web (Tomcat 11)                         │
│  ├── 登录/注册 (SHA-256)                             │
│  ├── 水质预测 → 调用 AI API                          │
│  ├── 仪表盘 (ECharts 可视化)                          │
│  ├── 历史记录 / 预警管理                              │
│  └── 数据库备份与恢复 (mysqldump)                     │
├─────────────────────────────────────────────────────┤
│  Python FastAPI (Port 8000)                         │
│  ├── Voting Ensemble 模型推理                        │
│  ├── 安全门规则引擎 (ML + 领域知识)                    │
│  └── 综合分析 / 模型解释                              │
├─────────────────────────────────────────────────────┤
│  MySQL 9.6 (water_quality_db)                       │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 快速启动

### 环境要求

| 组件 | 版本 |
|------|------|
| JDK | 26 |
| Tomcat | 11 |
| Maven | 3.9 |
| Python | 3.11+ |
| MySQL | 9.6 |

### 1. 启动 MySQL

确保 MySQL 服务正在运行（Windows 服务或手动启动）。

### 2. 构建并部署 Jakarta EE Web 应用

```bash
cd WaterQualitySystem
mvn package
# 将 target/*.war 复制到 Tomcat webapps/ 目录
# 重启 Tomcat
```

### 3. 启动 AI API 服务

```bash
cd WaterQualityAI
pip install -r requirements.txt
python ai_api.py
```

访问 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) 查看 API 文档。

### 4. 数据库初始化

```bash
mysql -uroot -p < mysql/water_quality_db.sql
```

---

## ✨ 功能特性

| 模块 | 功能 |
|------|------|
| 🔐 用户系统 | 注册、登录（SHA-256 密码哈希）、角色权限管理 |
| 🔮 AI 预测 | 7 种 ML 模型对比，Voting Ensemble 生产推理 |
| 🛡️ 安全门 | 9 项水质指标硬性阈值检测，领域知识 + ML 融合 |
| 📊 仪表盘 | ECharts 可视化：7 日趋势、来源统计、安全率 |
| 📋 历史记录 | 检测记录查询、详情查看、CSV 导出 |
| ⚠️ 预警管理 | 超标自动预警、处理状态跟踪 |
| 💾 备份恢复 | mysqldump 全库备份、快照恢复（仅管理员） |
| 📖 知识库 | 水质标准参考、模型信息对比 |

---

## 📂 项目结构

```
├── WaterQualitySystem/          Jakarta EE Web 应用
│   ├── src/main/java/.../       Servlet + DAO + Filter
│   ├── src/main/webapp/         JSP 前端页面
│   └── pom.xml                  Maven 配置
│
├── WaterQualityAI/              Python AI 微服务
│   ├── ai_api.py                FastAPI 主入口
│   ├── model_train.py           模型训练与评估（重复交叉验证 + 配对比较）
│   ├── data_preprocess.py       预处理链 / 概率标定 / 特征分析
│   ├── best_model.pkl           生产模型（预处理+Voting集成，单个 Pipeline）
│   ├── probability_calibrator.pkl  概率标定曲线（sigmoid）
│   ├── model_metrics.json       指标与评估协议（接口从这里读，不写死在源码）
│   └── requirements.txt         Python 依赖
│
├── mysql/                       数据库脚本
│   ├── water_quality_db.sql     建库 + 示例数据
│   └── backup_manual.sql        备份恢复 SQL 手册
│
└── CLAUDE.md                    开发者指南
```

---

## 🔧 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | JSP, ECharts, Crystal Design System |
| 后端 | Jakarta EE 6.0, JDBC, Servlet |
| AI | Python FastAPI, scikit-learn, LightGBM, XGBoost |
| 数据库 | MySQL 9.6 (InnoDB) |
| 安全 | SHA-256 密码哈希, Session 认证, 环境变量管理凭证 |

---

## 🤖 AI 模型

使用 **Voting Ensemble**（SVM + 随机森林 Soft Voting）+ **sigmoid 概率标定**作为生产模型，在 3,276 条水质数据上训练。数据处理流程：

```
原始数据 → 中位数缺失值填充 → StandardScaler 标准化 → Voting Ensemble 训练
→ 袋外概率拟合 sigmoid 标定曲线 → 宏平均 F1 选决策阈值
```

类别不均衡（正类 39%）用 `class_weight='balanced'` / `scale_pos_weight` 处理，
**不使用 SMOTE**：15 折重复交叉验证里 SMOTE 让 AUC 掉 0.004~0.006，还会把决策阈值推到 0.6 以上。

### 指标口径

指标一律以 **5 折 × 3 次重复交叉验证**（全量 3276 条，每折在自身训练部分内部完成标定与定阈值）为主口径；
固定 20% 留出（656 条）只作对照——单次留出的 AUC 标准误约 ±0.02，比模型之间的差距还大，
用它判断"谁更准"会得出随机结论。运行 `python model_train.py` 可完整复现下表与 `model_metrics.json`。

| 模型 | 准确率 | F1 | AUC | 说明 |
|------|--------|-----|-----|------|
| 集成学习Voting（生产） | **0.6641** ±0.0049 | 0.5573 | **0.7025** ±0.0048 | 新流程 |
| 旧线上模型（RF200+SMOTE+KNN，阈值 0.5） | 0.6274 ±0.0050 | 0.5381 | 0.6723 ±0.0044 | 优化前，实际部署的 pkl |
| 旧文档模型（RF+SVM+LightGBM+SMOTE，阈值 0.5） | 0.6568 ±0.0041 | 0.5531 | 0.6930 ±0.0043 | 优化前，README 声称的那个 |
| 多数类基线（全部判为不合格） | 0.6099 | — | 0.5 | 参照下限 |

生产模型相对"旧线上模型"的 15 折**配对**差值：准确率 +0.0367（p=0.0035）、F1 +0.0192（p=0.0002）、
宏平均 F1 +0.0303（p=0.0026）、AUC +0.0302（p=0.0019）。
相对"旧文档模型"只有 AUC 提升显著（+0.0095，p=0.047），F1 差异在噪声内（p=0.65）——
即真正拿到手的是"模型换成 SVM+RF 集成 + 不泄漏的阈值"这部分的收益，
而不是与旧 README 里那套并未部署的配置相比翻盘。

这份数据的信号本身较弱，AUC 约 0.70 已接近该数据集公开研究的水平；
提升应看作"同一份数据、同一协议下的稳定增益"，而不是绝对精度已经很高。

---

## 📄 许可证

本项目仅用于课程设计学习目的。

---

## 👥 作者

[@Xiaoyuan-114](https://github.com/Xiaoyuan-114) · 2026
