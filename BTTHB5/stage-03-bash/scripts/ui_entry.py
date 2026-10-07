"""Khởi tạo adapter provider trước mỗi lượt chạy UI; app/agent mẫu giữ nguyên."""
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from scripts.model_runtime import configure_model
configure_model()
runpy.run_path(str(root / 'app.py'), run_name='__main__')
