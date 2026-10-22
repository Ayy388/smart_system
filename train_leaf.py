import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras import layers, models
import os

# 数据加载
train_ds = tf.keras.utils.image_dataset_from_directory(
    'dataset',
    image_size=(224, 224),
    batch_size=16,
    validation_split=0.2,
    subset="training",
    seed=42
)
val_ds = tf.keras.utils.image_dataset_from_directory(
    'dataset',
    image_size=(224, 224),
    batch_size=16,
    validation_split=0.2,
    subset="validation",
    seed=42
)

# 数据增强
data_augmentation = tf.keras.Sequential([
    layers.RandomFlip("horizontal"),
    layers.RandomRotation(0.1),
    layers.RandomZoom(0.1),
])

# 加载预训练MobileNetV2（冻结骨干网络）
base_model = MobileNetV2(input_shape=(224, 224, 3),
                          include_top=False,
                          weights='imagenet')
base_model.trainable = False

# 构建分类模型
model = models.Sequential([
    data_augmentation,
    layers.Rescaling(1./127.5, offset=-1),
    base_model,
    layers.GlobalAveragePooling2D(),
    layers.Dropout(0.2),
    layers.Dense(2, activation='softmax')  # 健康/病害
])

model.compile(optimizer='adam',
              loss='sparse_categorical_crossentropy',
              metrics=['accuracy'])

print("开始训练（冻结骨干网络）...")
history = model.fit(train_ds, validation_data=val_ds, epochs=10)

# 保存模型
model.save("leaf_model.keras")
print("模型已保存为 leaf_model.keras")

# 转换为TFLite
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
tflite_model = converter.convert()

with open("leaf_model.tflite", "wb") as f:
    f.write(tflite_model)
print("TFLite模型已保存为 leaf_model.tflite")

# 打印验证准确率
val_loss, val_acc = model.evaluate(val_ds)
print(f"验证准确率: {val_acc:.4f}")
