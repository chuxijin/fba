import os
import sys
from pathlib import Path

# Add the project root to the sys.path to allow importing backend modules
# Assuming the script is run from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.core.path_conf import BASE_PATH

def find_task_packages():
    packages = []
    task_dir = os.path.join(BASE_PATH, 'app', 'task', 'tasks')
    print(f"DEBUG: BASE_PATH: {BASE_PATH}")
    print(f"DEBUG: task_dir: {task_dir}")
    for root, dirs, files in os.walk(task_dir):
        if 'tasks.py' in files:
            print(f"DEBUG: Found tasks.py in root: {root}")
            package = root.replace(str(BASE_PATH.parent) + os.path.sep, '').replace(os.path.sep, '.')
            packages.append(package)
            print(f"DEBUG: Generated package: {package}")
    return packages

if __name__ == "__main__":
    print("Detected Celery task packages:")
    for pkg in find_task_packages():
        print(pkg) 