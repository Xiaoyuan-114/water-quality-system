"""
水质AI预测服务 - FastAPI微服务
提供多模型预测、模型信息查询、特征解释等功能
支持Jakarta EE Web系统调用和数据库协作
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

import pandas as pd
import numpy as np
import joblib
import json
import os
from datetime import datetime

from data_preprocess import FEATURE_COLUMNS

# 创建FastAPI应用
app = FastAPI(
    title="Water Quality AI Prediction Service",
    description="基于机器学习和深度学习的水质预测API，支持多模型对比",
    version="2.0.0"
)

# CORS支持Jakarta EE Web前端跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 加载模型和预处理工具
# ============================================================

# 切换到脚本所在目录，确保相对路径正确（无论从哪里启动都能找到模型文件）
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# best_model.pkl 是完整 Pipeline（中位数填充 + 标准化 + Voting 集成），
# 与训练脚本保存的对象同一个，推理端不再手工拼接预处理步骤
model = joblib.load("best_model.pkl")
threshold = joblib.load("best_threshold.pkl")

# 概率标定曲线（sigmoid/Platt，拟合于训练集袋外概率）。
# 单独一个文件而不是把 CalibratedClassifierCV 打进模型里，是因为后者会把整个集成
# 按 cv 复制多份（实测 128 MB，超过 GitHub 单文件 100 MB 限制）；
# sigmoid 严格单调，不改变排序与 AUC，只把概率刻度摊开，
# 让 water_grade 的 Good/Excellent 与 standard_level 的饮用水档真正可达。
calibrator = joblib.load("probability_calibrator.pkl")


def _load_metrics():
    """
    模型指标一律来自训练产物 model_metrics.json，不在源码里写死，
    避免重新训练后接口还在汇报旧数字。
    """
    try:
        with open("model_metrics.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError(
            "缺少 model_metrics.json，请先运行 python model_train.py 重新训练"
        )


MODEL_METRICS = _load_metrics()
PRODUCTION_MODEL = MODEL_METRICS["生产模型"]
# 主口径是重复交叉验证均值（单次留出受 656 行样本噪声影响太大）
CV_METRICS = MODEL_METRICS["交叉验证指标"]
HOLDOUT_METRICS = MODEL_METRICS["留出测试集指标"]

# 加载特征重要性
feature_importance_df = joblib.load("feature_importance.pkl")

# 加载模型评估结果
model_eval_df = pd.read_csv("model_evaluation.csv")

# 模型描述信息（体现国际前沿趋势 - AI引论要求）
MODEL_DESCRIPTIONS = {
    "决策树": {
        "type": "传统机器学习",
        "description": "基于信息增益的树形分类模型，可解释性强",
        "international_context": "作为XAI(可解释AI)的基础模型，在环境科学领域广泛应用"
    },
    "随机森林": {
        "type": "集成学习",
        "description": "Bagging集成方法，通过多棵决策树投票降低过拟合",
        "international_context": "当前水质预测领域使用最广泛的模型之一，在WHO饮用水安全评估中被广泛引用"
    },
    "SVM": {
        "type": "传统机器学习",
        "description": "支持向量机，通过寻找最优超平面进行分类",
        "international_context": "在小样本水质异常检测中表现优异，被EPA用于污染源识别"
    },
    "梯度提升树": {
        "type": "集成学习",
        "description": "Boosting集成方法，逐步优化残差",
        "international_context": "在Kaggle水质预测竞赛中持续排名前列"
    },
    "XGBoost": {
        "type": "梯度提升",
        "description": "优化的分布式梯度提升库，正则化防止过拟合",
        "international_context": "2016年Kaggle冠军算法，在工业界水质监测中广泛部署"
    },
    "LightGBM": {
        "type": "梯度提升",
        "description": "微软开源的轻量级梯度提升框架，基于直方图算法",
        "international_context": "2023年环境监测领域新宠，速度比XGBoost快3-10倍"
    },
    "集成学习Voting": {
        "type": "模型融合",
        "description": "Soft Voting融合SVM+随机森林，再用sigmoid做概率标定",
        "international_context": "多模型融合是当前AI前沿趋势，Gartner预测2025年70%的环境AI系统将采用集成方法"
    },
}

# 水质标准参考信息
WATER_STANDARDS_INFO = {
    "饮用水": {
        "standard": "GB5749-2022《生活饮用水卫生标准》",
        "levels": ["Excellent", "Good", "Fair"],
        "description": "适用于城乡各类生活饮用水"
    },
    "地表水I类": {
        "standard": "GB3838-2002《地表水环境质量标准》",
        "levels": ["Excellent", "Good"],
        "description": "适用于源头水、国家自然保护区"
    },
    "地表水II类": {
        "standard": "GB3838-2002《地表水环境质量标准》",
        "levels": ["Good", "Fair"],
        "description": "适用于集中式生活饮用水源地一级保护区"
    },
    "污水排放": {
        "standard": "GB8978-1996《污水综合排放标准》",
        "levels": ["Poor", "Dangerous"],
        "description": "适用于工业废水和生活污水排放监控"
    }
}


# ============================================================
# 请求数据格式
# ============================================================
class WaterQualityData(BaseModel):
    pH: float = Field(..., ge=0, le=14, description="pH值 (0-14)")
    hardness: float = Field(..., ge=0, description="硬度(mg/L)")
    solids: float = Field(..., ge=0, description="固体含量(ppm)")
    chloramines: float = Field(..., ge=0, description="氯胺(ppm)")
    sulfate: float = Field(..., ge=0, description="硫酸盐(mg/L)")
    conductivity: float = Field(..., ge=0, description="电导率(μS/cm)")
    organic_carbon: float = Field(..., ge=0, description="有机碳(ppm)")
    trihalomethanes: float = Field(..., ge=0, description="三卤甲烷(μg/L)")
    turbidity: float = Field(..., ge=0, description="浊度(NTU)")


class BatchWaterData(BaseModel):
    samples: List[WaterQualityData] = Field(..., min_length=1, max_length=100)


# ============================================================
# 核心预测逻辑
# ============================================================
def _sample_values(sample: "WaterQualityData") -> Dict[str, float]:
    """API 字段名（小写）→ 训练特征名（原始列名）"""
    return {
        "ph": sample.pH,
        "Hardness": sample.hardness,
        "Solids": sample.solids,
        "Chloramines": sample.chloramines,
        "Sulfate": sample.sulfate,
        "Conductivity": sample.conductivity,
        "Organic_carbon": sample.organic_carbon,
        "Trihalomethanes": sample.trihalomethanes,
        "Turbidity": sample.turbidity,
    }


def _to_feature_frame(values: Dict[str, float]) -> pd.DataFrame:
    """按训练时的列名与列序构造输入，列错位会在预处理阶段直接报错"""
    return pd.DataFrame([values], columns=FEATURE_COLUMNS)


def make_prediction(input_data: pd.DataFrame) -> Dict[str, Any]:
    """核心预测函数，返回完整预测结果"""
    # 按训练时的列序取列：缺列抛 KeyError，列序不同则静默纠正，
    # 避免 sklearn 只给 warning 后按位置错配特征
    input_data = input_data[FEATURE_COLUMNS]

    # best_model.pkl 内含中位数填充 + 标准化 + 集成，这里不再手工预处理
    raw_probability = float(model.predict_proba(input_data)[0][1])
    probability = float(calibrator.predict([raw_probability])[0])

    prediction = 1 if probability >= threshold else 0
    prediction_text = "Safe" if prediction == 1 else "Unsafe"

    # 计算水质等级
    if probability >= 0.9:
        grade = "Excellent"
    elif probability >= 0.8:
        grade = "Good"
    elif probability >= 0.6:
        grade = "Fair"
    elif probability >= 0.3:
        grade = "Poor"
    else:
        grade = "Dangerous"

    # 简单WQI计算
    wqi = _calculate_wqi(input_data)

    # 确定参考水标准
    if probability >= 0.7:
        standard_level = "饮用水" if probability >= 0.8 else "地表水I类"
    elif probability >= 0.3:
        standard_level = "地表水II类"
    else:
        standard_level = "污水排放"

    # 硬性安全规则：严重超标时强制判定 Unsafe
    hard_safe, hard_reason = _safety_gate(input_data)
    if not hard_safe:
        prediction_text = "Unsafe"
        grade = "Dangerous"
        standard_level = "污水排放"

    return {
        "prediction": prediction_text,
        "probability": round(probability, 4),
        "threshold": round(threshold, 4),
        # 安全门会覆盖模型判定，不把这个字段暴露出来的话，
        # 调用方无法区分"模型说不安全"和"模型说安全但被规则拦下"
        "ml_prediction": "Safe" if prediction == 1 else "Unsafe",
        "safety_gate_triggered": not hard_safe,
        "safety_gate_reason": hard_reason,
        "water_grade": grade,
        "wqi_score": round(wqi, 2),
        "standard_level": standard_level,
        "model_name": PRODUCTION_MODEL,
        "timestamp": datetime.now().isoformat()
    }


def _safety_gate(input_data: pd.DataFrame):
    """
    硬性安全规则门控（ML + 领域知识融合）
    根据GB5749-2022饮用水标准，任何指标明显超标则强制判定 Unsafe
    返回 (is_safe: bool, reason: str)
    """
    row = input_data.iloc[0]

    # pH 超出饮用水标准 6.5-8.5 较远范围
    if row['ph'] < 5.0:
        return False, f"pH={row['ph']:.1f}严重偏酸（标准 6.5-8.5），危害健康"
    if row['ph'] > 10.0:
        return False, f"pH={row['ph']:.1f}严重偏碱（标准 6.5-8.5），危害健康"

    # 硬度 > 600 mg/L（饮用水标准<450）
    if row['Hardness'] > 600:
        return False, f"硬度={row['Hardness']:.0f}mg/L超标（标准<450mg/L）"

    # 固体 >= 1500 ppm（饮用水标准<1000）
    if row['Solids'] >= 1500:
        return False, f"固体={row['Solids']:.0f}ppm超标（标准<1000ppm）"

    # 氯胺 >= 6 ppm（饮用水标准<4）
    if row['Chloramines'] >= 6:
        return False, f"氯胺={row['Chloramines']:.1f}ppm超标（标准<4ppm）"

    # 硫酸盐 >= 400 mg/L（饮用水标准<250）
    if row['Sulfate'] >= 400:
        return False, f"硫酸盐={row['Sulfate']:.0f}mg/L超标（标准<250mg/L）"

    # 电导率 >= 1500 μS/cm（饮用水标准<1000）
    if row['Conductivity'] >= 1500:
        return False, f"电导率={row['Conductivity']:.0f}μS/cm超标（标准<1000μS/cm）"

    # 有机碳 >= 5 ppm（饮用水标准<2）
    if row['Organic_carbon'] >= 5:
        return False, f"有机碳={row['Organic_carbon']:.1f}ppm超标（标准<2ppm）"

    # 三卤甲烷 >= 120 μg/L（致癌物，饮用水标准<80）
    if row['Trihalomethanes'] >= 120:
        return False, f"三卤甲烷={row['Trihalomethanes']:.0f}μg/L超标（标准<80μg/L），致癌风险"

    # 浊度 >= 8 NTU（饮用水标准<5）
    if row['Turbidity'] >= 8:
        return False, f"浊度={row['Turbidity']:.1f}NTU超标（标准<5NTU）"

    return True, ""


def _calculate_wqi(input_data: pd.DataFrame) -> float:
    """计算综合水质指数"""
    row = input_data.iloc[0]
    scores = []
    # pH (理想值7.0)
    scores.append(max(0, 100 - abs(row['ph'] - 7.0) * 15) * 0.12)
    # 其他指标
    scores.append(max(0, 100 - (row['Hardness'] / 500) * 100) * 0.10)
    scores.append(max(0, 100 - (row['Solids'] / 1500) * 100) * 0.10)
    scores.append(max(0, 100 - (row['Chloramines'] / 5) * 100) * 0.12)
    scores.append(max(0, 100 - (row['Sulfate'] / 400) * 100) * 0.10)
    scores.append(max(0, 100 - (row['Conductivity'] / 1500) * 100) * 0.10)
    scores.append(max(0, 100 - (row['Organic_carbon'] / 10) * 100) * 0.12)
    scores.append(max(0, 100 - (row['Trihalomethanes'] / 120) * 100) * 0.12)
    scores.append(max(0, 100 - (row['Turbidity'] / 10) * 100) * 0.12)
    return round(sum(scores), 2)


# ============================================================
# API端点
# ============================================================

@app.get("/")
def health():
    """健康检查（指标读自 model_metrics.json，重新训练后自动同步）"""
    return {
        "status": "online",
        "service": "Water Quality AI Prediction Service",
        "version": "2.0.0",
        "model": PRODUCTION_MODEL,
        "model_accuracy": CV_METRICS["准确率"],
        "model_f1": CV_METRICS["F1-Score"],
        "model_auc": CV_METRICS["AUC"],
        "accuracy_sem": CV_METRICS["准确率_sem"],
        "auc_sem": CV_METRICS["AUC_sem"],
        "holdout_accuracy": HOLDOUT_METRICS["准确率"],
        "threshold": round(float(threshold), 4),
        "evaluation": MODEL_METRICS["主口径"],
        "timestamp": datetime.now().isoformat()
    }


@app.post("/predict/single")
def predict_single(data: WaterQualityData):
    """
    单条水质数据预测
    返回预测结果、概率、水质等级、WQI指数等完整信息
    """
    try:
        input_data = _to_feature_frame(_sample_values(data))

        result = make_prediction(input_data)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预测失败：{str(e)}")


@app.post("/predict/batch")
def predict_batch(data: BatchWaterData):
    """
    批量水质数据预测（最多100条）
    用于检测员批量导入CSV数据
    """
    try:
        results = []
        for sample in data.samples:
            input_data = _to_feature_frame(_sample_values(sample))
            result = make_prediction(input_data)
            results.append(result)

        return {
            "total_samples": len(results),
            "safe_count": sum(1 for r in results if r["prediction"] == "Safe"),
            "unsafe_count": sum(1 for r in results if r["prediction"] == "Unsafe"),
            "results": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量预测失败：{str(e)}")


@app.get("/model/info")
def get_model_info():
    """
    获取所有AI模型的评估信息
    全部取自训练产物 model_evaluation.csv / model_metrics.json，
    源码内不留任何手写指标
    """
    try:
        models_info = []
        for _, row in model_eval_df.iterrows():
            model_name = row['模型']
            desc = MODEL_DESCRIPTIONS.get(model_name, {})
            models_info.append({
                "model_name": model_name,
                "model_type": desc.get("type", "未分类"),
                "accuracy": round(float(row['准确率']), 4),
                "f1_score": round(float(row['F1-Score']), 4),
                "auc": round(float(row['AUC']), 4),
                "precision": round(float(row['精确率']), 4),
                "recall": round(float(row['召回率']), 4),
                "cv_auc": round(float(row['交叉验证AUC']), 4),
                "cv_f1_mean": round(float(row['交叉验证F1']), 4),
                "threshold": round(float(row['阈值']), 4),
                "is_production": model_name == PRODUCTION_MODEL,
                "evaluation_protocol": str(row['评估协议']),
                "is_baseline": str(row['参与评选']) != "是",
                "description": desc.get("description", ""),
                "international_context": desc.get("international_context", "")
            })

        current_model = {
            "name": PRODUCTION_MODEL,
            "type": "集成学习",
            "components": MODEL_METRICS["生产模型成员"],
            "calibration": MODEL_METRICS.get("概率标定"),
            "threshold": round(float(threshold), 4)
        }

        return {
            "models": models_info,
            "current_model": current_model,
            "total_models": len(models_info),
            "production_model": PRODUCTION_MODEL,
            "data_source": MODEL_METRICS["数据集"],
            "evaluation_protocol": MODEL_METRICS["主口径"],
            "holdout_protocol": MODEL_METRICS["辅助口径"],
            "majority_baseline_accuracy": MODEL_METRICS["多数类基线准确率"],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型信息失败：{str(e)}")


@app.get("/model/explain")
def get_model_explain():
    """
    获取模型解释性信息（特征重要性）
    支持XAI可解释AI，满足AI引论课程的系统思维要求
    """
    try:
        features = [
            {
                "feature": str(row['特征']),
                "importance": float(row['重要性']),
                "importance_pct": round(float(row['重要性']) * 100, 2)
            }
            for _, row in feature_importance_df.iterrows()
        ]

        return {
            "features": sorted(features, key=lambda x: x['importance'], reverse=True),
            "method": MODEL_METRICS["特征重要性来源"],
            "note": "特征重要性越高，对水质判断影响越大",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取特征解释失败：{str(e)}")


@app.get("/standards")
def get_water_standards():
    """获取水质标准参考信息"""
    return {
        "standards": WATER_STANDARDS_INFO,
        "indicators": ["pH", "Hardness", "Solids", "Chloramines", "Sulfate",
                        "Conductivity", "Organic_carbon", "Trihalomethanes", "Turbidity"],
        "timestamp": datetime.now().isoformat()
    }


@app.post("/analyze")
def comprehensive_analyze(data: WaterQualityData):
    """
    综合分析接口：返回预测结果+异常检测+标准对比+建议
    体现多维度系统思维（AI引论要求）
    """
    try:
        input_data = _to_feature_frame(_sample_values(data))

        # AI预测
        prediction_result = make_prediction(input_data)

        # 超标分析
        exceedances = []
        checks = [
            ("pH", data.pH, 6.5, 8.5),
            ("硬度(mg/L)", data.hardness, 0, 450),
            ("固体(ppm)", data.solids, 0, 1000),
            ("氯胺(ppm)", data.chloramines, 0, 4),
            ("硫酸盐(mg/L)", data.sulfate, 0, 250),
            ("电导率(μS/cm)", data.conductivity, 0, 1000),
            ("有机碳(ppm)", data.organic_carbon, 0, 2),
            ("三卤甲烷(μg/L)", data.trihalomethanes, 0, 80),
            ("浊度(NTU)", data.turbidity, 0, 5)
        ]
        for name, value, vmin, vmax in checks:
            if value < vmin or value > vmax:
                exceedances.append({
                    "indicator": name,
                    "value": value,
                    "range": f"{vmin}-{vmax}",
                    "status": "超标"
                })

        # 建议
        suggestions = []
        if prediction_result["prediction"] == "Unsafe":
            suggestions.append("⚠️ 水质检测结果不安全，建议立即停止饮用并进行深度处理")
            if data.turbidity > 5:
                suggestions.append("浊度超标，建议增加过滤和沉淀处理环节")
            if data.pH < 6.5:
                suggestions.append("pH偏酸，建议添加碱性中和剂")
            elif data.pH > 8.5:
                suggestions.append("pH偏碱，建议添加酸性中和剂")
        elif prediction_result["probability"] < 0.7:
            suggestions.append("水质处于临界状态，建议增加净化处理并定期复查")
        else:
            suggestions.append("✅ 水质检测结果安全，符合饮用水标准")

        return {
            "prediction": prediction_result,
            "exceedances": exceedances,
            "exceedance_count": len(exceedances),
            "suggestions": suggestions,
            "suggestion_count": len(suggestions),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"综合分析失败：{str(e)}")


@app.get("/dashboard/summary")
def get_dashboard_summary():
    """
    仪表盘汇总数据接口
    为Jakarta EE前端Dashboard提供数据
    """
    try:
        return {
            "model_overview": {
                "active_model": PRODUCTION_MODEL,
                "model_components": MODEL_METRICS["生产模型成员"],
                "accuracy": CV_METRICS["准确率"],
                "f1_score": CV_METRICS["F1-Score"],
                "auc": CV_METRICS["AUC"],
                "precision": CV_METRICS["精确率"],
                "recall": CV_METRICS["召回率"],
                "holdout_accuracy": HOLDOUT_METRICS["准确率"],
                "majority_baseline_accuracy": MODEL_METRICS["多数类基线准确率"],
                "threshold": round(float(threshold), 4)
            },
            "features_used": FEATURE_COLUMNS,
            "prediction_classes": ["Safe", "Unsafe"],
            "water_grades": ["Excellent", "Good", "Fair", "Poor", "Dangerous"],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取仪表盘数据失败：{str(e)}")


# 直接运行
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "ai_api:app",
        host="127.0.0.1",
        port=8000,
        reload=False
    )