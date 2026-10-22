# test_db.py
from db_init import init_db
from db_helper import DBHelper

init_db()
db = DBHelper()

# 插入测试记录
db.insert_detection("test1.jpg", "healthy", 0.95, {"ratio": 0.02})
db.insert_detection("test2.jpg", "diseased", 0.87, {"ratio": 0.15})

# 查询历史
history = db.get_history(10)
print("历史记录:")
for row in history:
    print(row)

# 统计
stats = db.get_statistics()
print(f"\n统计: {stats}")
