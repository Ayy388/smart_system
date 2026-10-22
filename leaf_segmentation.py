import cv2
import numpy as np

def segment_leaf(image):
    """输入BGR图像，返回叶片二值掩膜"""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_green = np.array([25, 40, 40])
    upper_green = np.array([95, 255, 255])
    mask = cv2.inRange(hsv, lower_green, upper_green)
    kernel_small = np.ones((3, 3), np.uint8)
    kernel_large = np.ones((7, 7), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_small)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_large)
    return mask

def find_leaf_contour(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < 500:
        return None
    return largest

def detect_disease(leaf_mask, original_image):
    """输入叶片掩膜和原图，返回病害掩膜和病害面积占比"""
    hsv = cv2.cvtColor(original_image, cv2.COLOR_BGR2HSV)
    lower_disease = np.array([10, 60, 40])
    upper_disease = np.array([25, 255, 255])
    disease_mask = cv2.inRange(hsv, lower_disease, upper_disease)
    disease_mask = cv2.bitwise_and(disease_mask, disease_mask, mask=leaf_mask)
    kernel = np.ones((3, 3), np.uint8)
    disease_mask = cv2.morphologyEx(disease_mask, cv2.MORPH_OPEN, kernel)
    leaf_area = np.sum(leaf_mask > 0)
    disease_area = np.sum(disease_mask > 0)
    ratio = disease_area / leaf_area if leaf_area > 0 else 0
    return disease_mask, ratio
