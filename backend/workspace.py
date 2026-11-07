from __future__ import annotations

import os
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

from . import core

MANIFEST_NAME = '.thangmia_manifest.json'
CONFIG_PATH = Path.home() / '.thangmia' / 'workspace-config.json'


def workspace_root() -> Path:
    configured = os.environ.get('THANGMIA_WORKSPACE_DIR')
    if configured:
        return Path(configured).expanduser()
    if CONFIG_PATH.exists():
        try:
            configured = json.loads(CONFIG_PATH.read_text(encoding='utf-8')).get('workspace_dir')
        except (OSError, ValueError, TypeError):
            configured = None
        if configured:
            return Path(configured).expanduser()
    return Path('~/.thangmia/workspace').expanduser()


def _absolute_root(path: Path | None = None) -> Path:
    root = (path or workspace_root()).expanduser()
    if not root.is_absolute():
        raise ValueError('THANGMIA_WORKSPACE_DIR phải là đường dẫn tuyệt đối.')
    if root.exists() and root.is_symlink():
        raise ValueError('Workspace không được là symbolic link.')
    return root


def _hash_text(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def _manifest_path(root: Path) -> Path:
    return root / MANIFEST_NAME


def _read_manifest(root: Path) -> dict[str, dict]:
    path = _manifest_path(root)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Không đọc được manifest workspace: {exc}') from exc
    return raw if isinstance(raw, dict) else {}


def _write_json_safely(path: Path, payload: object) -> None:
    _write_text_safely(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _record_key(date: str, ai: int, slot: int) -> str:
    return f'{date}|AI{ai}|{slot:02d}'


def _file_names(date: str, ai: int, slot: int) -> tuple[str, str]:
    prefix = f'{date}_AI{ai}_{slot:02d}'
    return f'{prefix}.txt', f'{prefix}_output.txt'


def _local_slot(ai: int, global_slot: int) -> int:
    if ai not in (1, 2, 3) or not (1 <= global_slot <= 42):
        raise ValueError('Lane hoặc slot không hợp lệ.')
    local_slot = global_slot - ((ai - 1) * 14)
    if not 1 <= local_slot <= 14:
        raise ValueError('Slot không thuộc lane AI đã chọn.')
    return local_slot


def _validate_slot(items: Iterable[dict], ai: int, slot: int) -> dict:
    if not 1 <= slot <= 14:
        raise ValueError('Slot trong lane phải từ 01 đến 14.')
    item = next((candidate for candidate in items if candidate.get('slot') == (ai - 1) * 14 + slot), None)
    if item is None or item.get('ai') != ai or not item.get('uid'):
        raise ValueError('Không tìm thấy brief hợp lệ cho lane và slot đã chọn.')
    return item


def check_workspace(path: Path | None = None) -> dict[str, object]:
    root = _absolute_root(path)
    root.mkdir(parents=True, exist_ok=True)
    lane_status = {}
    for ai in (1, 2, 3):
        lane = root / f'AI{ai}'
        lane_status[f'AI{ai}'] = {'path': str(lane), 'exists': lane.is_dir(), 'readable': os.access(lane, os.R_OK),
                                  'writable': os.access(lane, os.W_OK)}
    probe = root / '.thangmia-write-test.tmp'
    try:
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
        writable = True
    except OSError:
        writable = False
    return {'folder': str(root.resolve()), 'exists': root.is_dir(), 'readable': os.access(root, os.R_OK),
            'writable': writable, 'lanes': lane_status}


def set_workspace(path: str) -> dict[str, object]:
    root = _absolute_root(Path(path))
    check = check_workspace(root)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    os.environ['THANGMIA_WORKSPACE_DIR'] = str(root.resolve())
    _write_json_safely(CONFIG_PATH, {'workspace_dir': str(root.resolve()), 'updated_at': datetime.now(timezone.utc).isoformat()})
    return check


def _lane_path(ai: int) -> tuple[Path, Path]:
    root = _absolute_root()
    lane = root / f'AI{ai}'
    if lane.exists() and lane.is_symlink():
        raise ValueError('Thư mục lane không được là symbolic link.')
    return root, lane


def _safe_lane_dir(root: Path, ai: int) -> Path:
    root = _absolute_root(root)
    if root.exists() and root.is_symlink():
        raise ValueError('Thư mục workspace không được là symbolic link.')
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    lane_dir = root / f'AI{ai}'
    if lane_dir.exists() and lane_dir.is_symlink():
        raise ValueError('Thư mục lane không được là symbolic link.')
    lane_dir.mkdir(exist_ok=True)
    if lane_dir.resolve().parent != root:
        raise ValueError('Đường dẫn lane nằm ngoài workspace.')
    return lane_dir


def _write_text_safely(path: Path, content: str) -> None:
    if path.exists() and path.is_symlink():
        raise ValueError(f'Tập tin symbolic link không được phép: {path.name}')
    with tempfile.NamedTemporaryFile(
        mode='w', encoding='utf-8', newline='', dir=path.parent, prefix=f'.{path.stem}.', suffix='.tmp', delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        temporary.write(content)
        temporary.flush()
        os.fsync(temporary.fileno())
    try:
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def export_lane(date: str, ai: int, items: Iterable[dict], templates: dict[str, str]) -> dict[str, object]:
    lane = sorted(items, key=lambda item: item.get('slot', 0))
    expected_slots = set(range(1, 15))
    local_slots = {_local_slot(ai, item.get('slot', 0)) for item in lane}
    if len(lane) != 14 or local_slots != expected_slots:
        raise ValueError(f'AI {ai} phải có đúng 14 brief với slot duy nhất từ 01 đến 14.')
    core.validate_prompt_template(templates.get('full', ''))
    if not templates.get('full', '').strip():
        raise ValueError('Chưa cấu hình template full. Hãy mở Cài đặt Prompt để nhập và lưu template.')

    root = _absolute_root()
    lane_dir = _safe_lane_dir(root, ai)
    manifest = _read_manifest(root)
    written = 0
    skipped = 0
    for item in lane:
        local_slot = _local_slot(ai, item['slot'])
        input_name, output_name = _file_names(date, ai, local_slot)
        input_path = lane_dir / input_name
        output_path = lane_dir / output_name
        if input_path.exists() or output_path.exists():
            skipped += 1
            continue
        prompt = core.render_prompt(item, 'full', templates)
        _write_text_safely(input_path, prompt)
        manifest[_record_key(date, ai, local_slot)] = {
            'date': date, 'ai': ai, 'slot': local_slot, 'uid': item['uid'],
            'prompt_filename': input_name, 'output_filename': output_name,
            'prompt_hash': _hash_text(prompt), 'prompt_version': 1,
            'output_hash': None, 'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        written += 1
    _write_json_safely(_manifest_path(root), manifest)
    return {'written': written, 'skipped': skipped, 'folder': str(lane_dir)}


def lane_status(date: str, ai: int, items: Iterable[dict]) -> list[dict[str, object]]:
    root, lane = _lane_path(ai)
    manifest = _read_manifest(root) if root.exists() else {}
    result = []
    for slot in range(1, 15):
        item = _validate_slot(items, ai, slot)
        input_name, output_name = _file_names(date, ai, slot)
        input_path, output_path = lane / input_name, lane / output_name
        record = manifest.get(_record_key(date, ai, slot))
        warnings = []
        if record is None and (input_path.exists() or output_path.exists()):
            warnings.append('Thiếu metadata ánh xạ cho file workspace.')
        elif record and record.get('uid') != item['uid']:
            warnings.append('UID trong metadata không còn khớp brief hiện tại.')
        result.append({'slot': slot, 'uid': item['uid'], 'prompt_filename': input_name,
                       'output_filename': output_name, 'prompt_exists': input_path.is_file(),
                       'output_exists': output_path.is_file(), 'prompt_hash': record.get('prompt_hash') if record else None,
                       'output_hash': _hash_text(output_path.read_text(encoding='utf-8')) if output_path.is_file() else None,
                       'warnings': warnings})
    return result


def read_file(date: str, ai: int, slot: int, kind: Literal['prompt', 'output'], items: Iterable[dict]) -> dict[str, object]:
    root, lane = _lane_path(ai)
    item = _validate_slot(items, ai, slot)
    records = _read_manifest(root)
    record = records.get(_record_key(date, ai, slot))
    input_name, output_name = _file_names(date, ai, slot)
    filename = input_name if kind == 'prompt' else output_name
    path = lane / filename
    if not record:
        if not path.exists():
            return {'content': '', 'filename': filename, 'hash': None, 'uid': item['uid'],
                    'exists': False, 'warning': 'File chưa được xuất; chưa có metadata ánh xạ.'}
        raise ValueError('File tồn tại nhưng không có metadata hợp lệ để ánh xạ với brief.')
    if record.get('uid') != item['uid']:
        raise ValueError('UID trong metadata không còn khớp brief hiện tại.')
    if not path.is_file():
        return {'content': '', 'filename': filename, 'hash': None, 'uid': item['uid'], 'exists': False}
    content = path.read_text(encoding='utf-8')
    return {'content': content, 'filename': filename, 'hash': _hash_text(content), 'uid': item['uid'], 'exists': True}


def write_file(date: str, ai: int, slot: int, kind: Literal['prompt', 'output'], content: str,
               expected_hash: str | None, items: Iterable[dict]) -> dict[str, object]:
    root, lane = _lane_path(ai)
    item = _validate_slot(items, ai, slot)
    records = _read_manifest(root)
    record = records.get(_record_key(date, ai, slot))
    if not record or record.get('uid') != item['uid']:
        raise ValueError('Không có metadata hợp lệ để ánh xạ file với brief.')
    input_name, output_name = _file_names(date, ai, slot)
    path = lane / (input_name if kind == 'prompt' else output_name)
    current_hash = _hash_text(path.read_text(encoding='utf-8')) if path.is_file() else None
    if expected_hash is not None and current_hash != expected_hash:
        raise FileExistsError('File đã thay đổi; tải lại trước khi lưu.')
    if not path.is_file():
        raise FileNotFoundError(f'Chưa có file {path.name}.')
    _write_text_safely(path, content)
    record['prompt_hash' if kind == 'prompt' else 'output_hash'] = _hash_text(content)
    if kind == 'prompt':
        record['prompt_version'] = int(record.get('prompt_version', 1)) + 1
    record['updated_at'] = datetime.now(timezone.utc).isoformat()
    _write_json_safely(_manifest_path(root), records)
    return {'filename': path.name, 'hash': record['prompt_hash' if kind == 'prompt' else 'output_hash']}


def delete_file(date: str, ai: int, slot: int, kind: Literal['prompt', 'output'], items: Iterable[dict]) -> dict[str, str]:
    root, lane = _lane_path(ai)
    item = _validate_slot(items, ai, slot)
    records = _read_manifest(root)
    record = records.get(_record_key(date, ai, slot))
    if not record or record.get('uid') != item['uid']:
        raise ValueError('Không có metadata hợp lệ để ánh xạ file với brief.')
    input_name, output_name = _file_names(date, ai, slot)
    path = lane / (input_name if kind == 'prompt' else output_name)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('Đường dẫn file không hợp lệ.')
    if path.exists():
        path.unlink()
    if kind == 'prompt':
        record['prompt_hash'] = None
    else:
        record['output_hash'] = None
    _write_json_safely(_manifest_path(root), records)
    return {'filename': path.name}
