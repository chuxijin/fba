import requests
from pathlib import Path

# 目标文件路径
TARGET_DIR = Path(__file__).resolve().parent / 'backend' / 'data'
TARGET_FILE = TARGET_DIR / 'exercises.json'

URL = 'https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json'

def download_file():
    print(f"准备下载动作库数据到: {TARGET_FILE}")
    
    # 确保目录存在
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        response = requests.get(URL, timeout=30)
        response.raise_for_status()
        
        with open(TARGET_FILE, 'wb') as f:
            f.write(response.content)
            
        print("✅ 下载成功！")
        
        # 简单检查数据量
        import json
        with open(TARGET_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"数据总条数: {len(data)}")
            if len(data) > 0:
                print(f"示例动作: {data[0].get('name')}")
                
    except Exception as e:
        print(f"❌ 下载失败: {e}")

if __name__ == '__main__':
    download_file()
