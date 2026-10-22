# ai_module_leaf.py
import tensorflow as tf
import cv2
import numpy as np
import os
from db_helper import DBHelper

# 初始化数据库
db = DBHelper()

MODEL_PATH = "leaf_model.tflite"
CLASS_NAMES = ["healthy", "diseased"]
INPUT_SIZE = (224, 224)

# 加载TFLite模型
interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

def predict_image(img_path):
    if not os.path.exists(img_path):
        print(f"错误：文件 {img_path} 不存在！")
        return None, None

    # 读取图片、预处理
    img = cv2.imread(img_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, INPUT_SIZE)
    img = img.astype(np.float32) / 127.5 - 1.0
    input_data = np.expand_dims(img, axis=0)

    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()
    output_data = interpreter.get_tensor(output_details[0]['index'])[0]

    pred_idx = int(np.argmax(output_data))
    label = CLASS_NAMES[pred_idx]
    confidence = float(output_data[pred_idx])

    # 写入数据库
    db.insert_detection(
        image_path=img_path,
        result_label=label,
        confidence=confidence,
        detail_info={"raw_score": output_data.tolist()}
    )
    return label, confidence

if __name__ == "__main__":
    # 从你的dataset里面选一张来测试，这里拿healthy里一张举例
    test_img = "dataset/healthy/001.JPG"
    # test_img = "dataset/diseased/xxx.jpg"

    label, conf = predict_image(test_img)
    if label is not None:
        print(f"识别结果：{label}，置信度：{conf:.4f}")

