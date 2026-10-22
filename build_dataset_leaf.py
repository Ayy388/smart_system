import cv2
import numpy as np
import os
import time
from camera_utils import create_camera, capture_frame
from leaf_segmentation import segment_leaf

# 创建数据集目录
os.makedirs("dataset/healthy", exist_ok=True)
os.makedirs("dataset/diseased", exist_ok=True)

picam2 = create_camera(640, 480)
print("按 'h' 保存健康叶片，按 'd' 保存病害叶片，按 'q' 退出")

healthy_count = len(os.listdir("dataset/healthy"))
diseased_count = len(os.listdir("dataset/diseased"))
print(f"已有样本：健康 {healthy_count}，病害 {diseased_count}")

while True:
    frame = capture_frame(picam2)
    leaf_mask = segment_leaf(frame)

    # 用掩膜裁剪叶片区域
    contours, _ = cv2.findContours(leaf_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        if w > 50 and h > 50:  # 最小尺寸过滤
            roi = frame[y:y+h, x:x+w]
            roi_resized = cv2.resize(roi, (224, 224))
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

    cv2.putText(frame, f"H:{healthy_count} D:{diseased_count}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.imshow("Dataset Builder", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('h') and contours:
        healthy_count += 1
        cv2.imwrite(f"dataset/healthy/{healthy_count:03d}.jpg", roi_resized)
        print(f"已保存健康样本 {healthy_count}")
    elif key == ord('d') and contours:
        diseased_count += 1
        cv2.imwrite(f"dataset/diseased/{diseased_count:03d}.jpg", roi_resized)
        print(f"已保存病害样本 {diseased_count}")
    elif key == ord('q'):
        break

picam2.stop()
cv2.destroyAllWindows()
print(f"最终样本数：健康 {healthy_count}，病害 {diseased_count}")
