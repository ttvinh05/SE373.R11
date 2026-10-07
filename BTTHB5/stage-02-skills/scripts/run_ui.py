"""Mở giao diện Streamlit; có thể dùng file cấu hình model ngoài bài nộp."""
import argparse
import os
from pathlib import Path
import sys

from streamlit.web import cli


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--port', type=int, default=8501)
    args = parser.parse_args()
    if args.env_file:
        if not args.env_file.is_file():
            parser.error('Không tìm thấy file cấu hình model.')
        os.environ['LAB_MODEL_ENV_FILE'] = str(args.env_file.resolve())
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.argv = ['streamlit', 'run', str(root / 'app.py'), '--server.address=127.0.0.1', f'--server.port={args.port}']
    cli.main()


if __name__ == '__main__':
    main()
