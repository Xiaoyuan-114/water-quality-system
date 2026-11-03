import joblib

# 特征顺序现在直接从生产模型（完整 Pipeline）里读，
# 不再依赖单独的 selected_features.pkl，避免两份定义漂移
try:
    model = joblib.load("best_model.pkl")
    scaler = model.named_steps["preprocessor"].named_steps["scaler"]
    features = list(scaler.get_feature_names_out())

    print("="*50)
    print("✅ 成功加载生产模型")
    print("="*50)
    print("模型结构：")
    print("-"*50)
    print(model)
    print("-"*50)
    print("训练时使用的特征顺序（非常重要！）：")
    print("-"*50)
    for i, feature in enumerate(features, 1):
        print(f"{i}. {feature}")
    print("="*50)
    print("⚠️  预测时必须严格按照这个顺序输入数值！")
    print("="*50)
except FileNotFoundError:
    print("❌ 错误：找不到best_model.pkl文件")
    print("请确保你在WaterQualityAI文件夹中运行此脚本，"
          "或先运行 python model_train.py 重新训练")
except Exception as e:
    print(f"❌ 发生错误：{type(e).__name__}: {str(e)}")

# 按回车键退出
input("\n按回车键退出...")