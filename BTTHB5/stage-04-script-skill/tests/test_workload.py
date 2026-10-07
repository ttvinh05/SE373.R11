import json
import subprocess
import sys

import pytest

import paths

SCRIPT = paths.FIXTURES_DIR / 'skills/csv-quality/scripts/check_csv.py'


def run(path, threshold='8'):
    args = [sys.executable, str(SCRIPT), '--input', str(path)]
    if threshold is not None:
        args += ['--max-hours', threshold]
    return subprocess.run(args, capture_output=True, text=True, timeout=10)


@pytest.mark.parametrize('threshold,overloaded', [('8', [{'owner': 'Lan', 'total_hours': 9}]), ('9', [])])
def test_workload_threshold_and_excluded_rows(threshold, overloaded):
    source = paths.FIXTURES_DIR / 'data/workload.csv'
    before = source.read_bytes()
    result = run(source, threshold)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['hours_by_owner'] == {'Lan': 9, 'Minh': 3}
    assert data['overloaded_owners'] == overloaded
    assert data['excluded_rows'] == [
        {'line': 5, 'task_id': 'T04', 'reasons': ['invalid_hours']},
        {'line': 6, 'task_id': 'T02', 'reasons': ['duplicate_id']},
        {'line': 7, 'task_id': 'T05', 'reasons': ['missing_owner']},
    ]
    assert source.read_bytes() == before
    assert data['row_count'] == 6


def test_first_invalid_id_still_blocks_later_valid_duplicate():
    result = run(paths.FIXTURES_DIR / 'data/workload-edge.csv', '0')
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['hours_by_owner'] == {'Minh': 0}
    assert data['overloaded_owners'] == []
    assert data['excluded_rows'] == [
        {'line': 2, 'task_id': 'E01', 'reasons': ['invalid_hours']},
        {'line': 3, 'task_id': 'E01', 'reasons': ['duplicate_id']},
    ]


@pytest.mark.parametrize('threshold', [None, '-1', 'nan', 'inf', 'abc', ''])
def test_threshold_required_finite_nonnegative(threshold):
    result = run(paths.FIXTURES_DIR / 'data/workload.csv', threshold)
    assert result.returncode != 0
    assert result.stderr
    assert not result.stdout


def test_all_reasons_order_trimming_case_and_quality_of_excluded_rows(tmp_path):
    path = tmp_path / 'mixed.csv'
    path.write_text('task_id,owner,hours\n X , Lan , 1 \nX,,bad,extra\n,,bad,extra\nY,lan,0\nZ,Minh,2\n\n')
    data = json.loads(run(path, '1').stdout)
    assert data['hours_by_owner'] == {'Lan': 1, 'Minh': 2, 'lan': 0}
    assert data['overloaded_owners'] == [{'owner': 'Minh', 'total_hours': 2}]
    assert data['excluded_rows'] == [
        {'line': 3, 'task_id': 'X', 'reasons': ['wrong_field_count', 'duplicate_id', 'missing_owner', 'invalid_hours']},
        {'line': 4, 'task_id': None, 'reasons': ['wrong_field_count', 'missing_task_id', 'missing_owner', 'invalid_hours']},
    ]
    assert data['invalid_hours_count'] == 2
    assert data['missing_owner_count'] == 2
    assert data['row_count'] == 5
