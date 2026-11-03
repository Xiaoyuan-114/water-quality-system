# Water Quality AI System — Project Guide

## Stack
- WaterQualitySystem/ — Jakarta EE 6.0 WAR (Tomcat 11, JDK 26, Maven 3.9)
- WaterQualityAI/ — Python FastAPI on port 8000
- MySQL 9.6 on localhost:3306, db=water_quality_db, root/<your_db_password>

## Quick Start
```bash
# 1. Start MySQL (should already be running as Windows service)

# 2. Build & deploy Jakarta EE WAR
cd WaterQualitySystem
mvn package
# Copy target/*.war to <tomcat>/webapps/
# Restart Tomcat: <tomcat>/bin/shutdown.bat && <tomcat>/bin/startup.bat

# 3. Start AI API
cd WaterQualityAI
water_ai_env\Scripts\python ai_api.py
# API docs: http://127.0.0.1:8000/docs
```

## Key Files
| File | Purpose |
|------|---------|
| `LoginServlet.java` | User login + `sha256()` password verify + last login time update |
| `RegisterServlet.java` | User registration with JDBC transaction (`FOR UPDATE` lock) |
| `PredictServlet.java` | Core: parse 9 params → call AI API → parse JSON → save to DB |
| `DashboardServlet.java` | Dashboard stats (total/safe/unsafe) + 7-day trend + source stats |
| `BackupServlet.java` | Admin-only DB backup/restore (mysqldump + mysql via ProcessBuilder) |
| `AuthFilter.java` | Session check filter — redirects to login.jsp for protected paths |
| `EncodingFilter.java` | UTF-8 encoding filter for all requests |
| `DetectionDAO.java` | Insert detection record with explicit JDBC transaction |
| `DBUtil.java` | DB connection pool + SHA-256 hash utility |
| `web.xml` | Filter chain order: EncodingFilter → AuthFilter |
| `ai_api.py` | FastAPI: 8 endpoints, ML pipeline + safety gate + WQI calculation |
| `dashboard.jsp` | ECharts line chart (7-day trend) + bar chart (source stats) |
| `model_info.jsp` | ECharts radar chart (model comparison) + bar chart (accuracy rank) |

## Environment
- JAVA_HOME: `<your_jdk_path>`
- MAVEN_HOME: `<your_maven_path>`
- Tomcat: `<your_tomcat_path>`
- MySQL: `<your_mysql_path>`
- Python venv: `WaterQualityAI\water_ai_env\`

## Recent changes (2026-06-14)
- `665d9ba` fix: 最后登录时间更新改用 `UPDATE users SET last_login_time=NOW()`，Copyright 年份改为 2016-2017
- `f33d9bb` fix: 回退到 `insideTop` + 均值线去掉标签文字（遵循 ECharts 约定）
- `cccbbbd` fix: 均值从 markLine 标签移到卡片标题显示——**markLine text label 在 bar chart 上必然裁切**

## Model & metrics (Python side)

- 产物都在 `WaterQualityAI/`，由 `python model_train.py` 生成（约 15 分钟）：
  `best_model.pkl`（Pipeline：中位数填充 + 标准化 + SVM/RF Voting 集成）、
  `probability_calibrator.pkl`（袋外概率上的 sigmoid 标定曲线）、`best_threshold.pkl`、
  `model_evaluation.csv`、`model_metrics.json`。
  **ai_api.py 的指标一律读 `model_metrics.json`，不要在源码里写死准确率。**
- 前端展示的模型指标另有来源：MySQL 表 `ai_model_info`（seed 在
  `mysql/water_quality_db.sql`；`dashboard.jsp` / `model_info.jsp` 读库，不读 Python 产物）。
  重训之后要同步那张表，SQL 文件里备好了一组 UPDATE 语句。
- 评估协议 = 5折×3次重复交叉验证，每折只在自己的训练分片内部做标定和定阈值。
  **不要退回"在测试集上搜阈值 / 按测试集 F1 选模型"**：旧版那么做，报出的 0.5899 准确率
  连"全部判不合格"的 0.610 多数类基线都不如，而且 `best_model.pkl` 实际是随机森林、
  文档却写 Voting Ensemble——选模型和报指标用同一份数据就是泄漏。
- 产物体积有硬约束：GitHub 单文件 100 MB。`CalibratedClassifierCV(cv=5)` 会把整个集成复制 5 份
  （实测 128 MB，push 直接被拒），所以标定曲线单独存成约 1 KB 的 pkl；`best_model.pkl` 用 `compress=3` 落盘（约 10.5 MB）。
- 已知问题（未改，属产品决策）：安全门的 Solids 上限是 1500 ppm，而本数据集 Solids 中位数约 2 万，
  于是数据集里每一行都会触发安全门、API 恒返回 Unsafe，模型概率在输出标签上完全看不出来。
  现在响应里用 `ml_prediction` / `safety_gate_triggered` / `safety_gate_reason` 把两者分工暴露出来，
  真要修的是阈值与数据单位口径，不是模型。

## Before editing code
- For risky changes, branch first: `git checkout -b <name>` → work → merge back → delete branch
- User prefers: explain the design plan first, then implement after approval

## JSP conventions
- All pages use `template_header.jsp` + `template_footer.jsp` (Crystal design system, CSS prefix `c-`)
- `sendRedirect()` must be followed by `return` in JSP scriptlets
- Navigation dropdown hover fix: use `::before` pseudo-element on the menu itself, NOT `::after` + `pointer-events:none` on the parent

## JDBC conventions
- Transaction pattern: `conn.setAutoCommit(false)` → operations → `conn.commit()` or `conn.rollback()` → finally restore auto-commit and close all resources
- Password storage: `DBUtil.sha256()` — never store plaintext
- `SELECT ... FOR UPDATE` for row-level locking when checking+inserting

## Database backup
- `mysqldump -uroot -p<your_password> --single-transaction --routines --triggers --set-gtid-purged=OFF --databases water_quality_db --result-file=<path>`
- `mysql -uroot -p<your_password> water_quality_db < <file>` (feed via stdin with ProcessBuilder, NOT redirection)
- **Must include `--set-gtid-purged=OFF`** — otherwise restore fails with MySQL ERROR 3546 (GTID conflict)

## Deploy workflow
- **JSP only changes**: may auto-compile via Tomcat hot-deploy (timestamp detection)
- **Java changes** (Servlet, etc): MUST run `mvn package` in `WaterQualitySystem/`, copy WAR to Tomcat `webapps/`, restart Tomcat
- Changing both: always full deploy

## Testing
- `WaterQualityAI/test_api.py` — Quick API endpoint tests (single predict, batch predict, model info)
- `WaterQualityAI/generate_test_data.py` — Generate CSV test data for batch testing
- `WaterQualityAI/test_data_50samples.csv` / `test_results_50samples.csv` — Pre-generated test data and results
- Manual testing: 3 sample groups (safe / borderline / severely polluted) to verify safety gate behavior

## Frontend conventions
- **Form validation**: dual-layer — JS `onsubmit` (instant feedback) + Java backend `validateRange()` (anti-bypass)
  - Frontend ranges should be slightly wider than API safety gate thresholds (catch obvious typos only)
- **All AI API 9 water quality indicators already have safety gate thresholds** — no additional backend gates needed
- **ECharts**: bar chart labels use `position:'insideTop'` with `distance:8` to prevent clipping; use `yAxis.max` slightly above highest value
  - **Never use markLine with text labels** on bar charts — text always clips on the right; use a dashed line without label instead
- **Never fabricate data**: all displayed metrics must exist in the database; don't introduce hidden fields not shown in tables

## Git (user is a beginner)
- Key commands: status, add, commit, log, checkout -b, merge, reflog
- Each improvement commit message format: "feat: <description>" or "fix: <description>"
- `git checkout <commit-hash>` to go back to any historical version
