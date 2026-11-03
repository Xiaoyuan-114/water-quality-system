================================================================================
                          水质AI预测系统
                Water Quality AI Prediction System
                    人工智能引论 课程设计
================================================================================

【项目简介】

  本系统基于机器学习方法，对饮用水水质进行安全性预测（Potable / Not potable）。
  使用 7 种机器学习模型进行对比，最终采用 Voting Ensemble（投票集成）作为
  生产模型，并通过 FastAPI 提供 RESTful API 服务，供前端 Web 系统调用。

  数据集：water_potability.csv（3276条记录，9项水质指标）
  指标：pH值、硬度(Hardness)、固体(Solids)、氯胺(Chloramines)、
        硫酸盐(Sulfate)、电导率(Conductivity)、有机碳(Organic_carbon)、
        三卤甲烷(Trihalomethanes)、浊度(Turbidity)


【文件结构】

  WaterQualityAI/
  ├── ai_api.py              FastAPI 主服务（API 入口）
  ├── model_train.py         模型训练脚本（数据加载→预处理→训练→评估）
  ├── data_preprocess.py     预处理链 / 概率标定 / 特征分析
  ├── check_features.py      特征检查调试工具
  ├── water_potability.csv   原始数据集
  ├── model_evaluation.csv   模型评估指标汇总（含旧流程对照组）
  ├── requirements.txt       Python 依赖包列表
  ├── README.txt             本文件
  │
  ├── best_model.pkl         生产模型：预处理+Voting集成的完整 Pipeline（约10.5MB）
  ├── probability_calibrator.pkl  概率标定曲线（sigmoid，约1KB）
  ├── best_threshold.pkl     最优决策阈值（0.44）
  ├── model_metrics.json     指标与评估协议（ai_api.py 的指标来源）
  ├── feature_importance.pkl 特征重要性数据
  │
  ├── model_comparison.png   模型对比图
  ├── feature_importance.png 特征重要性图
  ├── feature_correlation.png特征相关性热力图
  ├── feature_distribution.png特征分布图
  └── 各模型混淆矩阵 + ROC曲线图（14张）


【环境要求】

  - Python 3.11+
  - 依赖包见 requirements.txt


【安装与运行】

  1. 创建并激活虚拟环境（推荐）

     python -m venv venv
     venv\Scripts\activate          # Windows
     # 或 source venv/bin/activate  # macOS/Linux

  2. 安装依赖

     pip install -r requirements.txt

  3. 启动 API 服务

     python ai_api.py

     服务启动后访问：http://127.0.0.1:8000
     API 文档（Swagger UI）：http://127.0.0.1:8000/docs


【API 接口说明】

  端点                             方法    说明
  ─────────────────────────────────────────────────────────
  /                                GET     服务状态检查
  /predict/single                  POST    单条水质预测
  /predict/batch                   POST    批量水质预测
  /model/info                      GET     查询所有模型信息
  /model/explain                   GET     特征重要性解释
  /standards                       GET     饮用水标准参考值
  /analyze                         POST    水样分析（含安全门检测）
  /dashboard/summary               GET     仪表盘汇总统计


【模型列表】

  指标口径：5折x3次重复交叉验证（全量3276条），每折在自身训练部分内部
  完成概率标定与定阈值；测试集不参与任何选择。运行 python model_train.py 可复现。

  序号  模型名称        模型类型        准确率     F1       AUC
  ──────────────────────────────────────────────────────────
  1     决策树          传统机器学习     62.0%     0.413    0.596
  2     随机森林        集成学习         65.8%     0.539    0.687
  3     SVM             传统机器学习     66.1%     0.554    0.696
  4     梯度提升树      集成学习         62.6%     0.490    0.648
  5     XGBoost         集成学习         63.5%     0.511    0.664
  6     LightGBM        集成学习         64.3%     0.512    0.669
  7     集成学习Voting  集成学习(生产)   66.4%     0.557    0.703
  ──────────────────────────────────────────────────────────
  对照  旧线上模型      RF200+SMOTE+KNN  62.7%     0.538    0.672
        （阈值固定0.5）
        多数类基线      全部判为不合格    61.0%        —      0.5

  这份数据的信号本身较弱，AUC 约 0.70 已接近该数据集公开研究的水平。
  单次 20% 留出（656条）的 AUC 标准误约 ±0.02，比模型之间的差距还大，
  所以 model_evaluation.csv 里同时给出留出列仅作参考，结论看 CV 均值。


【技术要点】

  - 数据预处理：中位数缺失值填充 → StandardScaler 标准化，与估计器一起存进
    同一个 Pipeline，杜绝训练/推理各做一半预处理导致的静默错位
  - 特征选择：原始只有 9 个特征，旧版 SelectKBest(k=9) 是空操作，已移除
  - 不平衡处理：用 class_weight='balanced' / scale_pos_weight，
    不使用 SMOTE（15折重复CV里 SMOTE 让 AUC 掉 0.004~0.006，还把阈值推到 0.6 以上）
  - 概率标定：在袋外概率上拟合 sigmoid(Platt) 曲线，严格单调所以 AUC 不变，
    只把概率刻度摊开，让 water_grade 的 Good/Excellent 档真正可达
  - 安全门机制：对 9 项水质指标设定安全阈值范围，超出范围直接判定为 Unsafe；
    接口同时返回 ml_prediction / safety_gate_reason，用于区分
    "模型判不安全" 与 "模型判安全但被规则拦下"
  - 模型持久化：使用 joblib 序列化，FastAPI 启动时加载至内存


【注意事项】

  - 首次运行需确保 best_model.pkl / probability_calibrator.pkl /
    best_threshold.pkl / feature_importance.pkl / model_evaluation.csv /
    model_metrics.json 与 ai_api.py 在同一目录下，缺任意一个服务会启动失败
    （宁可拒绝启动，也不要拿写死的旧指标对外返回）
  - 如需重新训练模型，运行 python model_train.py（约 15 分钟，含 15 折重复CV
    与配对显著性检验，产物全部覆盖写入）
  - 数据集路径默认当前目录，如移动位置需修改代码中的路径变量


【作者】

  水质AI检测团队
  2026年6月
