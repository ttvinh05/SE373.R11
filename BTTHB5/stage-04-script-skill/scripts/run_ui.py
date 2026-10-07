"""Mở Streamlit từ bản sao stage, hỗ trợ cấu hình model ngoài bài nộp."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--port', type=int, default=8501)
    args = parser.parse_args()
    if args.env_file and not args.env_file.is_file():
        parser.error('Không tìm thấy file cấu hình model.')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from scripts.model_runtime import configure_model
    settings, missing = configure_model(args.env_file)
    if missing:
        parser.error('Thiếu cấu hình: ' + ', '.join(missing))
    os.chdir(root)
    from streamlit.web import cli
    sys.argv = ['streamlit', 'run', str(root / 'scripts/ui_entry.py'), '--server.address=127.0.0.1', f'--server.port={args.port}']
    cli.main()


if __name__ == '__main__':
    main()
