import pandas as pd
import numpy as np
from sklearn.base import BaseEstimator
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split

# 注：matplotlib/seaborn 改为在 analyze_features() 内延迟 import，
# 使推理路径不依赖可视化库

# 训练与推理共用的特征顺序，任何一侧单独改动都会让线上预测静默错位
FEATURE_COLUMNS = [
    "ph", "Hardness", "Solids", "Chloramines", "Sulfate",
    "Conductivity", "Organic_carbon", "Trihalomethanes", "Turbidity",
]


# 1. 数据加载与基础清洗（仅去除重复值）
def load_data(file_path):

    df = pd.read_csv(file_path)

    # 去除重复值
    df = df.drop_duplicates()

    return df


# 2. 生产预处理链
#
# 用 Pipeline 而不是散落的 imputer.pkl / scaler.pkl / selector.pkl：
# 训练与推理共用同一个对象，杜绝"线上少做一步预处理"这类静默错位。
#
# 中位数填充替换了原来的 KNN 填充：同一随机森林配置下两者的袋外指标持平，
# 而 KNNImputer 要把整份训练矩阵存进 pkl（旧 imputer.pkl 213 KB，
# 对比 scaler 只有 783 B），并在每次预测时重新遍历它找邻居，代价换不来增益。
def build_preprocessor():

    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])


# 概率标定（Platt / sigmoid）
#
# 为什么不用 sklearn 的 IsotonicRegression：保序回归会在曲线上留下平台段，
# 平台段把不同的原始概率压成同一个标定值，留出集上的排序被打乱，
# 实测 AUC 掉约 0.01（与模型之间的差距同量级），等于拿指标损失换刻度好看。
# sigmoid 严格单调，任何数据上的排序与 AUC 都和未标定完全一致。
#
# 斜率非正说明"概率越高反而越不像可饮用"，那必然是训练异常，
# 此时退化为恒等变换，而不是把预测结果反向。
class ProbabilityCalibrator(BaseEstimator):

    def __init__(self, eps=1e-6):
        self.eps = eps

    def _logit(self, proba):
        p = np.clip(np.asarray(proba, dtype=float), self.eps, 1.0 - self.eps)
        return np.log(p / (1.0 - p)).reshape(-1, 1)

    def fit(self, proba, y):
        model = LogisticRegression().fit(self._logit(proba), np.asarray(y).astype(int))
        self.slope_ = float(model.coef_[0][0])
        self.identity_ = self.slope_ <= 0
        self.model_ = None if self.identity_ else model
        return self

    def predict(self, proba):
        proba = np.asarray(proba, dtype=float)
        if getattr(self, "identity_", True):
            return proba
        return self.model_.predict_proba(self._logit(proba))[:, 1]


# 3. 按固定列名取特征（列缺失立刻报错，不做静默补零）
def split_features(df, target_col="Potability"):

    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"缺少特征列: {missing}")

    X = df[FEATURE_COLUMNS].copy()
    y = None if target_col not in df.columns else df[target_col]

    return X, y


# 4. 特征分析与可视化
def analyze_features(df, target_col="Potability"):
    import matplotlib.pyplot as plt
    import seaborn as sns
    plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False

    # ==============================
    # 相关性分析可视化
    # ==============================
    plt.figure(figsize=(12, 8))

    sns.heatmap(
        df.corr(numeric_only=True),
        annot=True,
        cmap='coolwarm',
        fmt='.2f'
    )

    plt.title('水质特征相关性热力图')

    plt.savefig(
        'feature_correlation.png',
        dpi=300,
        bbox_inches='tight'
    )

    plt.close()

    # ==============================
    # 特征分布可视化
    # ==============================
    features = df.drop(target_col, axis=1).columns

    plt.figure(figsize=(15, 10))

    for i, feature in enumerate(features):

        plt.subplot(3, 3, i + 1)

        sns.histplot(
            data=df,
            x=feature,
            hue=target_col,
            kde=True
        )

        plt.title(f'{feature}分布')

    plt.tight_layout()

    plt.savefig(
        'feature_distribution.png',
        dpi=300,
        bbox_inches='tight'
    )

    plt.close()

    print("特征分析完成，已保存feature_correlation.png和feature_distribution.png")


# 测试代码
if __name__ == "__main__":

    # 加载本地数据集
    file_path = "water_potability.csv"

    print("数据集路径:", file_path)

    df = load_data(file_path)

    print("原始数据集形状：", df.shape)

    X, y = split_features(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    # 只在训练集上拟合预处理链
    preprocessor = build_preprocessor().fit(X_train, y_train)

    print("预处理完成，最终特征：",
          preprocessor.named_steps['scaler'].get_feature_names_out().tolist())

    print("训练集处理后形状：", preprocessor.transform(X_train).shape)

    print("测试集处理后形状：", preprocessor.transform(X_test).shape)

    # 特征分析
    analyze_features(df)
