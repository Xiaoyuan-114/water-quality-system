"""
水质预测模型训练（可饮用性二分类）

评估协议
--------
1. 主口径 = 全量数据 RepeatedStratifiedKFold(5折 x 3次 = 15折)。
   单次 656 行留出法的 AUC 标准误约 ±0.02，比模型间差距（约 0.01）还大，
   只用它判断"谁更准"会得到随机结论，因此改成重复交叉验证 + 配对比较。
2. 每一折都只用该折训练部分做三件事：拟合模型、拟合概率标定曲线、定决策阈值，
   然后才在该折留出部分计分 —— 完全复刻线上流程，
   杜绝旧版"在测试集上搜阈值 / 按测试集 F1 选模型"的泄漏。
   旧版阈值搜索区间是 0.45~0.65，而正类 F1 的真实峰值（约 0.42）在区间之外。
3. 同时保留一份固定 20% 留出结果（与历史 model_evaluation.csv 同口径，可对照）。
4. 产物三个文件，职责分明：
   - best_model.pkl            = 预处理(中位数填充+标准化) + Voting 集成，完整 Pipeline
   - probability_calibrator.pkl= 在袋外概率上拟合的 sigmoid(Platt) 标定曲线，约 1 KB
   - best_threshold.pkl        = 决策阈值
   标定曲线单独存放而不用 CalibratedClassifierCV(cv=5) 包一层，是因为后者会把
   整个集成按 cv 复制 5 份（实测产物 128 MB，超过 GitHub 单文件 100 MB 硬限制）。
   选 sigmoid 而不是 isotonic：isotonic 的平台段会把不同原始概率压成同一标定值，
   打乱留出集排序，实测 AUC 掉约 0.01；sigmoid 严格单调，AUC 与未标定时完全一致，
   只负责把概率刻度摊开，让 water_grade 的 Good/Excellent 档真正可达。

名字带"旧流程"前缀的行是对照组，不参与生产模型评选；带"@阈值0.5"的行
是旧版真实上线配置的行为复现，用于给出"优化前"数字。
"""

import json
import os
import platform
import shutil
import warnings
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from scipy.stats import ttest_rel

from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
    VotingClassifier,
)
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.impute import KNNImputer
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import (
    RepeatedStratifiedKFold,
    StratifiedKFold,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

from data_preprocess import (
    ProbabilityCalibrator,
    build_preprocessor,
    load_data,
    split_features,
)

warnings.filterwarnings("ignore")

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

RANDOM_STATE = 42
DATA_FILE = "water_potability.csv"
TARGET = "Potability"

# 与历史产物/前端表格保持同一套模型名，替换的只是估计器本身
PRODUCTION_CANDIDATES = [
    "决策树", "随机森林", "SVM", "梯度提升树", "XGBoost", "LightGBM", "集成学习Voting",
]
# 对照组：旧版真实部署流程的复刻，不参与生产评选
BASELINE_CANDIDATES = [
    "旧流程@阈值0.5:RF+SMOTE+KNN",
    "旧流程@阈值0.5:Voting+SMOTE+KNN",
    "旧流程同协议:RF+SMOTE+KNN",
    "旧流程同协议:Voting+SMOTE+KNN",
]
MODEL_NAMES = PRODUCTION_CANDIDATES + BASELINE_CANDIDATES

CLASS_WEIGHT = "balanced"
THRESHOLD_GRID = np.arange(0.30, 0.751, 0.005)
N_SPLITS = 5
N_REPEATS = 3
INNER_SPLITS = 3

# 旧版上线配置：阈值固定 0.5 且不做概率标定；新协议：袋外标定 + 宏平均F1定阈值
DEPLOYED_PROTOCOL = "deployed"
NESTED_PROTOCOL = "nested"


def protocol_of(name):
    return DEPLOYED_PROTOCOL if "@阈值0.5" in name else NESTED_PROTOCOL


# ============================================================
# 候选模型
# ============================================================
def is_baseline(name):
    return name in BASELINE_CANDIDATES


def build_model(name, pos_weight):
    """按名字构造估计器；每次调用返回全新实例，避免候选之间共享可变异对象。"""

    svm = lambda: SVC(C=3.0, gamma="scale", kernel="rbf", probability=True,
                      class_weight=CLASS_WEIGHT, random_state=RANDOM_STATE)
    rf = lambda: RandomForestClassifier(n_estimators=400, class_weight=CLASS_WEIGHT,
                                        random_state=RANDOM_STATE, n_jobs=-1)

    if name == "决策树":
        # 深树在这份弱信号数据上明显过拟合，袋外 AUC 搜索确定 max_depth=6
        return DecisionTreeClassifier(max_depth=6, min_samples_leaf=10,
                                      class_weight=CLASS_WEIGHT,
                                      random_state=RANDOM_STATE)

    if name == "随机森林":
        return rf()

    if name == "SVM":
        return svm()

    if name == "梯度提升树":
        return GradientBoostingClassifier(random_state=RANDOM_STATE)

    if name == "XGBoost":
        return XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.05,
                             subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
                             reg_lambda=2.0, scale_pos_weight=pos_weight,
                             eval_metric="logloss", tree_method="hist",
                             random_state=RANDOM_STATE, n_jobs=-1)

    if name == "LightGBM":
        return LGBMClassifier(n_estimators=300, max_depth=4, learning_rate=0.05,
                              num_leaves=15, min_child_samples=25, subsample=0.8,
                              subsample_freq=1, colsample_bytree=0.8, reg_lambda=2.0,
                              scale_pos_weight=pos_weight, verbose=-1,
                              random_state=RANDOM_STATE, n_jobs=-1)

    if name == "集成学习Voting":
        # 错误模式互补：15折 CV AUC Voting 0.7025 > SVM 单模 0.6956 > RF 单模 0.6919
        return VotingClassifier(estimators=[("svm", svm()), ("rf", rf())], voting="soft")

    if name.startswith("旧流程@阈值0.5:RF") or name.startswith("旧流程同协议:RF"):
        # 参数取自仓库里实际部署的 best_model.pkl（GridSearchCV(scoring='f1') 的结果）
        return RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=2,
                                      class_weight=CLASS_WEIGHT, random_state=42)

    if name.startswith("旧流程@阈值0.5:Voting") or name.startswith("旧流程同协议:Voting"):
        # README 声称的生产模型：RF + SVM(C=10) + LightGBM(is_unbalance) soft voting
        return VotingClassifier(estimators=[
            ("rf", RandomForestClassifier(n_estimators=200, class_weight=CLASS_WEIGHT,
                                          random_state=42, n_jobs=-1)),
            ("svm", SVC(C=10, gamma="scale", kernel="rbf", probability=True,
                        class_weight=CLASS_WEIGHT, random_state=42)),
            ("lgbm", LGBMClassifier(n_estimators=100, is_unbalance=True,
                                    random_state=42, verbose=-1, n_jobs=-1)),
        ], voting="soft")

    raise ValueError(f"未知模型: {name}")


def build_pipeline(name, pos_weight):
    """
    预处理与估计器绑成一个对象，训练/推理行为必然一致。
    对照组保留旧版的 KNN 填充 + SelectKBest(k=9) + SMOTE 链路，保证可比。
    """
    if is_baseline(name):
        # imblearn 的采样器要求链路上不能嵌套 Pipeline，因此这里摊平写
        return ImbPipeline([
            ("knn", KNNImputer(n_neighbors=5)),
            ("scaler", StandardScaler()),
            ("select", SelectKBest(f_classif, k=9)),
            ("smote", SMOTE(random_state=RANDOM_STATE)),
            ("clf", build_model(name, pos_weight)),
        ])

    return Pipeline([
        ("preprocessor", build_preprocessor()),
        ("clf", build_model(name, pos_weight)),
    ])


# ============================================================
# 概率标定与阈值
# ============================================================
def fit_calibrator(oof_proba, y_true):
    """在袋外概率上拟合 sigmoid(Platt) 标定曲线：严格单调，AUC 不变，只修正概率刻度。"""
    return ProbabilityCalibrator().fit(oof_proba, y_true)


def threshold_by_macro_f1(y_true, proba):
    """
    在袋外概率上按宏平均 F1 选阈值：两类都不允许被牺牲。
    只看传入的训练数据，不碰任何留出集。
    """
    scores = [f1_score(y_true, (proba >= t).astype(int), average="macro")
              for t in THRESHOLD_GRID]
    best = int(np.argmax(scores))
    return float(THRESHOLD_GRID[best]), float(scores[best])


def inner_oof_probabilities(name, X, y, pos_weight, n_splits=INNER_SPLITS):
    """袋外概率：拟合标定曲线与定阈值都用它。"""
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=RANDOM_STATE)
    total = np.zeros(len(y))
    for a, b in splitter.split(X, y):
        p = build_pipeline(name, pos_weight).fit(X.iloc[a], y[a])
        total[b] = p.predict_proba(X.iloc[b])[:, 1]
    return total


def fit_and_predict(name, X_fit, y_fit, X_pred, pos_weight, protocol):
    """
    在 (X_fit, y_fit) 上训练，返回 (X_pred 的概率, 决策阈值)。
    nested 协议下阈值与标定曲线都来自 X_fit 内部的袋外预测，X_pred 全程不参与。
    """
    pipe = build_pipeline(name, pos_weight).fit(X_fit, y_fit)
    raw = pipe.predict_proba(X_pred)[:, 1]

    if protocol == DEPLOYED_PROTOCOL:
        return raw, 0.5, pipe, None

    oof = inner_oof_probabilities(name, X_fit, y_fit, pos_weight)
    calibrator = fit_calibrator(oof, y_fit)
    threshold, _ = threshold_by_macro_f1(y_fit, calibrator.predict(oof))
    return calibrator.predict(raw), threshold, pipe, calibrator


def metrics_at(y_true, proba, threshold):
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "准确率": accuracy_score(y_true, pred),
        "F1-Score": f1_score(y_true, pred),
        "宏平均F1": f1_score(y_true, pred, average="macro"),
        "精确率": precision_score(y_true, pred, zero_division=0),
        "召回率": recall_score(y_true, pred),
        "AUC": roc_auc_score(y_true, proba),
        "TP": int(tp), "FP": int(fp), "FN": int(fn), "TN": int(tn),
    }


# ============================================================
# 两套评估：15 折重复 CV（主口径）+ 固定 20% 留出（历史口径）
# ============================================================
def cv_report(name, X, y, pos_weight):
    """每折独立标定并定阈值后，在留出部分计分；返回逐折指标。"""
    protocol = protocol_of(name)
    # 必须用 RepeatedStratifiedKFold：StratifiedKFold.split() 每次返回同一组划分，
    # 套一层 for rep 只是把同一次划分重跑三遍，标准误会被低估约 √3 倍
    outer = RepeatedStratifiedKFold(n_splits=N_SPLITS, n_repeats=N_REPEATS,
                                    random_state=RANDOM_STATE)
    y_arr = np.asarray(y)
    per_fold = []

    for i, (a, b) in enumerate(outer.split(X, y)):
        rep, fold = divmod(i, N_SPLITS)
        proba, thr, _, _ = fit_and_predict(
            name, X.iloc[a], y_arr[a], X.iloc[b], pos_weight, protocol
        )
        m = metrics_at(y_arr[b], proba, thr)
        m["阈值"] = thr
        # 同一 (rep, fold) 位置在各配置间是同一批划分，配对检验按 fold 聚合三次重复
        m["划分"] = fold
        m["重复"] = rep
        per_fold.append(m)

    return per_fold


def holdout_report(name, X_train, y_train, X_test, y_test, pos_weight):
    """与历史 model_evaluation.csv 同口径：80% 训练 / 20% 留出测试一次。"""
    proba, thr, _, _ = fit_and_predict(
        name, X_train, np.asarray(y_train), X_test, pos_weight, protocol_of(name)
    )
    m = metrics_at(np.asarray(y_test), proba, thr)
    m["阈值"] = thr
    return m, proba, (proba >= thr).astype(int)


def summarize(per_fold):
    df = pd.DataFrame(per_fold)
    out = {}
    for col in ["准确率", "F1-Score", "宏平均F1", "精确率", "召回率", "AUC", "阈值"]:
        out[col] = round(float(df[col].mean()), 4)
        out[f"{col}_sem"] = round(float(df[col].std(ddof=1) / np.sqrt(len(df))), 4)
    return out


def paired_compare(a_folds, b_folds, metric):
    """
    同一批划分上的配对比较。
    同一次 5 划分被重复取了 3 遍，重复之间不独立，
    所以先按划分求均值，只用 5 个近似独立的差值做配对 t 检验。
    """
    def by_partition(folds):
        return pd.DataFrame(folds).groupby("划分")[metric].mean().sort_index()

    a, b = by_partition(a_folds), by_partition(b_folds)
    t, p = ttest_rel(a, b)
    return {
        "指标": metric,
        "差值": round(float((a - b).mean()), 4),
        "差值标准误": round(float((a - b).std(ddof=1) / np.sqrt(len(a))), 4),
        "配对t": round(float(t), 3),
        "p值": round(float(p), 4),
    }


# ============================================================
# 图
# ============================================================
def plot_roc(y_true, proba, name):
    fpr, tpr, _ = roc_curve(y_true, proba)
    auc_score = roc_auc_score(y_true, proba)

    plt.figure(figsize=(6, 5))
    plt.plot(fpr, tpr, linewidth=2, label=f'AUC = {auc_score:.4f}')
    plt.plot([0, 1], [0, 1], linestyle='--')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title(f'{name} ROC Curve')
    plt.legend(loc='lower right')
    plt.savefig(f'{name}_roc_curve.png', dpi=300, bbox_inches='tight')
    plt.close()


def plot_confusion(y_true, pred, name):
    cm = confusion_matrix(y_true, pred)
    plt.figure(figsize=(6, 4))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=['不合格', '合格'], yticklabels=['不合格', '合格'])
    plt.title(f'{name}混淆矩阵')
    plt.ylabel('真实标签')
    plt.xlabel('预测标签')
    plt.savefig(f'{name}_confusion_matrix.png', dpi=300, bbox_inches='tight')
    plt.close()


def plot_comparison(result_df):
    plt.figure(figsize=(13, 6))
    x = np.arange(len(result_df["模型"]))
    width = 0.2
    plt.bar(x - width, result_df["准确率"], width, label='准确率')
    plt.bar(x, result_df["F1-Score"], width, label='F1-Score')
    plt.bar(x + width, result_df["AUC"], width, label='AUC')
    plt.xlabel('模型')
    plt.ylabel('得分')
    plt.title('模型性能对比（5折x3次重复交叉验证均值）')
    plt.xticks(x, result_df["模型"], rotation=25, ha="right", fontsize=8)
    plt.legend()
    plt.ylim(0, 1)
    plt.tight_layout()
    plt.savefig('model_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()


# ============================================================
# 说明性产物
# ============================================================
def describe_members(clf):
    """从实际训练出的对象里读出集成成员，供接口展示真实结构。"""
    return [name for name, _ in getattr(clf, "estimators", [])]


def analyze_feature_importance(X, y):
    """Voting 集成没有 feature_importances_，
    用同一条预处理链上的随机森林做代理模型，导出真实计算得到的 Gini 重要性。"""
    preprocessor = build_preprocessor().fit(X, y)
    rf = RandomForestClassifier(n_estimators=400, class_weight=CLASS_WEIGHT,
                                random_state=RANDOM_STATE, n_jobs=-1)
    rf.fit(preprocessor.transform(X), y)

    importance = pd.DataFrame({
        '特征': list(X.columns),
        '重要性': rf.feature_importances_,
    }).sort_values('重要性', ascending=False).reset_index(drop=True)

    plt.figure(figsize=(10, 6))
    sns.barplot(x='重要性', y='特征', data=importance)
    plt.title('特征重要性分析（随机森林代理模型）')
    plt.tight_layout()
    plt.savefig('feature_importance.png', dpi=300, bbox_inches='tight')
    plt.close()

    joblib.dump(importance, "feature_importance.pkl")
    print("\n特征重要性（代理随机森林）：")
    print(importance)
    return importance


def artifact_size(path):
    return round(os.path.getsize(path) / 1e6, 3) if os.path.exists(path) else None


# model_info.jsp 只能引用 WAR 内的图片，所以这两张图在仓库里有第二份。
# 靠人手复制必然漂移（曾经网页上挂的就是训练前的旧对比图），交给训练脚本同步。
WEBAPP_IMAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "WaterQualitySystem", "src", "main", "webapp", "images",
)
WEBAPP_SYNCED_IMAGES = ["model_comparison.png", "feature_importance.png"]


def sync_webapp_images():
    """把前端会引用的图同步到 WAR 目录。"""
    for name in WEBAPP_SYNCED_IMAGES:
        src = os.path.abspath(name)
        dst = os.path.join(WEBAPP_IMAGE_DIR, name)
        if os.path.exists(src):
            shutil.copyfile(src, dst)
            print(f"已同步 WAR 图片：{name} -> {dst}")
        else:
            print(f"警告：缺少 {src}，WAR 里的 {name} 仍是旧版")


def main():
    print("数据集路径:", DATA_FILE)
    df = load_data(DATA_FILE)
    X, y_df = split_features(df, TARGET)
    y = np.asarray(y_df.astype(int))
    print("原始数据集形状：", df.shape)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    pos_weight = float((y_train == 0).sum() / (y_train == 1).sum())
    print(f"训练集 {X_train.shape} / 测试集 {X_test.shape}，正类占比 {y_train.mean():.4f}"
          f"（多数类基线准确率 {1 - y_train.mean():.4f}）")

    rows, folds, holdouts = [], {}, {}

    for name in MODEL_NAMES:
        print(f"\n正在训练 {name}...", flush=True)

        fold_metrics = cv_report(name, X, y, pos_weight)
        folds[name] = fold_metrics
        cv = summarize(fold_metrics)

        hold, hold_proba, hold_pred = holdout_report(
            name, X_train, y_train, X_test, y_test, pos_weight
        )
        holdouts[name] = (hold, hold_proba, hold_pred)

        print(f"  CV(15折) 准确率={cv['准确率']:.4f}±{cv['准确率_sem']:.4f} "
              f"F1={cv['F1-Score']:.4f} 宏F1={cv['宏平均F1']:.4f} "
              f"AUC={cv['AUC']:.4f}±{cv['AUC_sem']:.4f} 阈值={cv['阈值']:.3f}")
        print(f"  留出(656) 准确率={hold['准确率']:.4f} F1={hold['F1-Score']:.4f} "
              f"AUC={hold['AUC']:.4f}")

        if name in PRODUCTION_CANDIDATES:
            y_true = np.asarray(y_test)
            plot_roc(y_true, hold_proba, name)
            plot_confusion(y_true, hold_pred, name)

        rows.append({
            "模型": name,
            "评估协议": "旧版线上配置(阈值0.5,无标定)" if protocol_of(name) == DEPLOYED_PROTOCOL
                        else "新协议(袋外标定+宏F1阈值)",
            "准确率": cv["准确率"],
            "F1-Score": cv["F1-Score"],
            "宏平均F1": cv["宏平均F1"],
            "AUC": cv["AUC"],
            "精确率": cv["精确率"],
            "召回率": cv["召回率"],
            "准确率标准误": cv["准确率_sem"],
            "AUC标准误": cv["AUC_sem"],
            "交叉验证AUC": cv["AUC"],
            "交叉验证F1": cv["F1-Score"],
            "阈值": cv["阈值"],
            "留出准确率": round(hold["准确率"], 4),
            "留出F1": round(hold["F1-Score"], 4),
            "留出AUC": round(hold["AUC"], 4),
            "参与评选": "是" if name in PRODUCTION_CANDIDATES else "否(对照)",
        })

    result_df = pd.DataFrame(rows)
    result_df.to_csv("model_evaluation.csv", index=False, encoding="utf-8-sig")
    print("\n评估结果（主口径=5折x3次重复交叉验证）：")
    print(result_df[["模型", "评估协议", "准确率", "F1-Score", "宏平均F1", "AUC",
                     "阈值", "留出准确率", "留出AUC", "参与评选"]].to_string(index=False))

    # ---------------- 生产模型评选：只看 CV AUC ----------------
    ranked = result_df[result_df["参与评选"] == "是"].sort_values("AUC", ascending=False)
    print("\n按 CV AUC 排序（生产候选）：")
    for _, r in ranked.iterrows():
        print(f"  {r['模型']:12s} AUC={r['AUC']:.4f} 准确率={r['准确率']:.4f} "
              f"宏F1={r['宏平均F1']:.4f} F1={r['F1-Score']:.4f}")
    production = ranked.iloc[0]["模型"]

    comparisons = []
    for baseline in BASELINE_CANDIDATES:
        comparisons.append({
            "对照组": baseline,
            "对照均值": dict(zip(
                ["准确率", "F1-Score", "宏平均F1", "AUC"],
                [result_df[result_df["模型"] == baseline][c].iloc[0]
                 for c in ["准确率", "F1-Score", "宏平均F1", "AUC"]])),
            "差值(生产模型-对照)": [
                paired_compare(folds[production], folds[baseline], m)
                for m in ["准确率", "F1-Score", "宏平均F1", "AUC"]
            ],
        })
    print(f"\n生产模型 {production} 相对各对照组的配对差异（同 15 折）：")
    for c in comparisons:
        print(" ", c["对照组"], c["对照均值"])
        for d in c["差值(生产模型-对照)"]:
            print(f"    {d['指标']:8s} {'+' if d['差值'] >= 0 else ''}{d['差值']:.4f} "
                  f"± {d['差值标准误']:.4f} (p={d['p值']:.4f})")

    plot_comparison(result_df)

    # ---------------- 定稿：全量重拟合 + 全量袋外标定与阈值 ----------------
    full_oof = inner_oof_probabilities(production, X, y, pos_weight, n_splits=N_SPLITS)
    calibrator = fit_calibrator(full_oof, y)
    threshold, macro_f1 = threshold_by_macro_f1(y, calibrator.predict(full_oof))

    pipe = build_pipeline(production, pos_weight).fit(X, y)

    joblib.dump(pipe, "best_model.pkl", compress=3)
    joblib.dump(calibrator, "probability_calibrator.pkl")
    joblib.dump(threshold, "best_threshold.pkl")

    members = describe_members(pipe.named_steps["clf"])
    print(f"\n生产模型：{production}，成员={members}，决策阈值={threshold:.3f}"
          f"（全量5折袋外宏平均F1={macro_f1:.4f}）")

    importance = analyze_feature_importance(X, y)
    sync_webapp_images()

    hold, hold_proba, _ = holdouts[production]
    production_cv = summarize(folds[production])
    calibrated_oof = calibrator.predict(full_oof)

    metrics = {
        "生成时间": datetime.now().isoformat(timespec="seconds"),
        "数据集": f"{DATA_FILE}（去重后 {len(df)} 条，9 项水质指标）",
        "主口径": f"{N_SPLITS}折x{N_REPEATS}次重复交叉验证（全量{len(df)}条），"
                  "每折在自身训练部分内部完成标定与定阈值",
        "辅助口径": "固定20%留出（656条，random_state=42），与历史表格同口径；"
                    "单次留出的AUC标准误约±0.02，仅作对照不作结论",
        "阈值规则": "袋外概率上的宏平均F1最大点（搜索区间0.30~0.75）",
        "生产模型": production,
        "生产模型成员": members,
        "概率标定": {
            "方法": "sigmoid(Platt)，拟合于全量5折袋外概率，存于 probability_calibrator.pkl",
            "斜率": round(float(calibrator.slope_), 4),
            "是否退化为恒等": bool(calibrator.identity_),
        },
        "预处理": "SimpleImputer(median) + StandardScaler（已并入 best_model.pkl）",
        "训练数据": f"全部 {len(df)} 条（评选、标定与定阈值均只用袋外预测，无留出泄漏）",
        "决策阈值": round(threshold, 4),
        "交叉验证指标": production_cv,
        "留出测试集指标": {k: (round(float(v), 4) if isinstance(v, float) else v)
                          for k, v in hold.items()},
        "对照比较": comparisons,
        "概率分布": {
            "说明": "留出测试集上的标定后概率分位数（未见数据，反映线上实际分布）",
            "p1": round(float(np.percentile(hold_proba, 1)), 4),
            "p50": round(float(np.percentile(hold_proba, 50)), 4),
            "p99": round(float(np.percentile(hold_proba, 99)), 4),
            "袋外p1": round(float(np.percentile(calibrated_oof, 1)), 4),
            "袋外p99": round(float(np.percentile(calibrated_oof, 99)), 4),
            "袋外占比_ge_0.8": round(float((calibrated_oof >= 0.8).mean()), 4),
            "袋外占比_ge_0.9": round(float((calibrated_oof >= 0.9).mean()), 4),
        },
        "多数类基线准确率": round(float(1 - y.mean()), 4),
        "特征重要性来源": "随机森林代理模型（Gini 重要性）",
        "特征重要性": {str(r["特征"]): round(float(r["重要性"]), 6)
                       for _, r in importance.iterrows()},
        "产物体积MB": {
            "best_model.pkl": artifact_size("best_model.pkl"),
            "probability_calibrator.pkl": artifact_size("probability_calibrator.pkl"),
            "best_threshold.pkl": artifact_size("best_threshold.pkl"),
        },
        "环境": {
            "python": platform.python_version(),
            "sklearn": __import__("sklearn").__version__,
        },
    }
    with open("model_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print("\n产物体积(MB):", metrics["产物体积MB"])
    print("\n生成文件：")
    for name in ["best_model.pkl", "probability_calibrator.pkl", "best_threshold.pkl",
                 "model_evaluation.csv", "model_metrics.json", "feature_importance.pkl",
                 "feature_importance.png", "model_comparison.png",
                 "*_roc_curve.png", "*_confusion_matrix.png"]:
        print("-", name)


if __name__ == "__main__":
    main()
