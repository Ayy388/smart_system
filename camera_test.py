import cv2
from picamera2 import Picamera2
import time

print("正在初始化摄像头...")
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(config)


picam2.start()
time.sleep(2)

print("摄像头启动成功！")
print("按 's' 键拍照保存，按 'q' 键退出")

while True:
    frame = picam2.capture_array()
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    cv2.imshow("Camera Test", frame_rgb)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('s'):
        picam2.capture_file("test_photo.jpg")
        print("照片已保存为 test_photo.jpg")
    elif key == ord('q'):
        break

cv2.destroyAllWindows()
picam2.stop()
print("程序结束")