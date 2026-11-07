"""THẮNG MIA API. Run: uvicorn backend.main:app --reload --port 8000"""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import core
from .store import DEFAULT_DATABASE_PATH, Store
from .workspace import (
    check_workspace, delete_file, export_lane, lane_status, read_file, set_workspace, write_file,
)

DEFAULT_PATH = Path(os.environ.get('THANGMIA_DB_PATH', str(DEFAULT_DATABASE_PATH))).expanduser()


def valid_date(date: str) -> str:
    try:
        if dt.date.fromisoformat(date).isoformat() != date:
            raise ValueError()
    except ValueError:
        raise HTTPException(422, 'Ngày phải theo định dạng YYYY-MM-DD hợp lệ.') from None
    return date


def get_day(db, date):
    day = db['days'].get(date)
    if day is None:
        raise HTTPException(404, 'Ngày làm việc chưa được tạo.')
    return day


def get_item(db, date, uid):
    return next((i for i in get_day(db, date)['items'] if i.get('uid') == uid), None) or _item_not_found()


def _item_not_found():
    raise HTTPException(404, 'Không tìm thấy thẻ cốt truyện.')


def metrics(items):
    counts = core.count_status(items)
    return {'total': len(items), 'done': counts['done'], 'in_progress': counts['sent'] + counts['part1'],
            'ready': counts['ready'], 'sent': counts['sent'], 'part1': counts['part1']}


def remaining_ideas(db):
    copied = sum(
        item.get('status') in ('sent', 'part1', 'done')
        for day in db['days'].values()
        for item in day['items']
    )
    return max(0, len(db['library']) - copied)


def validate_backup(raw):
    """Validate backup before write, not just its top-level version."""
    db = core.normalized_db(raw)
    ids = set()
    for i, brief in enumerate(db['library']):
        if not isinstance(brief, dict) or not isinstance(brief.get('id'), str) or not brief['id']:
            raise ValueError(f'library[{i}]: ID không hợp lệ.')
        if brief['id'] in ids:
            raise ValueError(f'library[{i}]: ID bị trùng.')
        ids.add(brief['id'])
        if brief.get('theme') not in core.THEME_NAME:
            raise ValueError(f'library[{i}]: nhóm chủ đề sai.')
        if any(not isinstance(brief.get(key), str) for key, _ in core.FIELDS):
            raise ValueError(f'library[{i}]: thiếu trường nội dung.')
    used_ids = set()
    for date, day in db['days'].items():
        valid_date(date)
        seen_uid, seen_slot = set(), set()
        for i, item in enumerate(day['items']):
            if not isinstance(item, dict) or not item.get('id') or not item.get('uid'):
                raise ValueError(f'{date} [{i}]: thiếu id hoặc uid.')
            if item['uid'] in seen_uid or item.get('slot') in seen_slot:
                raise ValueError(f'{date}: trùng uid hoặc slot.')
            seen_uid.add(item['uid'])
            seen_slot.add(item['slot'])
            if item['id'] in used_ids:
                raise ValueError(f'{date}: ID brief đã được sử dụng ở một ngày khác.')
            used_ids.add(item['id'])
            if item.get('theme') not in core.THEME_NAME or item.get('ai') not in (1, 2, 3):
                raise ValueError(f'{date} [{i}]: AI hoặc nhóm chủ đề không hợp lệ.')
            if item.get('status') not in core.STATUS_LABEL:
                raise ValueError(f'{date} [{i}]: trạng thái không hợp lệ.')
            if not isinstance(item['slot'], int) or not 1 <= item['slot'] <= 42:
                raise ValueError(f'{date} [{i}]: slot không hợp lệ.')
            if any(not isinstance(item.get(key), str) for key, _ in core.FIELDS):
                raise ValueError(f'{date} [{i}]: thiếu trường nội dung.')
    return db


class CreateDay(BaseModel):
    date: str


class Copied(BaseModel):
    mode: Literal['full', 'part1', 'part2']


class BriefEdit(BaseModel):
    title: str = Field(min_length=7, max_length=2000)
    hero: str = Field(min_length=7, max_length=2000)
    antagonist: str = Field(min_length=7, max_length=2000)
    conflict: str = Field(min_length=7, max_length=2000)
    evidence: str = Field(min_length=7, max_length=2000)
    reversal: str = Field(min_length=7, max_length=2000)
    ending: str = Field(min_length=7, max_length=2000)


class ImportPlan(BaseModel):
    ai: Literal[1, 2, 3]
    text: str = Field(min_length=1, max_length=100000)
    allow_similar: bool = False
    replace_ready: bool = False


class WorkspaceExport(BaseModel):
    date: str
    ai: Literal[1, 2, 3]


class WorkspaceConfig(BaseModel):
    folder: str


class WorkspaceFile(BaseModel):
    date: str
    ai: Literal[1, 2, 3]
    slot: int = Field(ge=1, le=14)
    kind: Literal['prompt', 'output']
    content: str
    expected_hash: str | None = None


def create_app(store: Store | None = None) -> FastAPI:
    database = store or Store(DEFAULT_PATH)
    app = FastAPI(title='thangmia API', version='3.0.0', description='Điều phối 42 brief/ngày, không gọi API AI.')

    @app.get('/api/health')
    def health():
        return {'ok': True, 'app': 'THẮNG MIA', 'version': '3.0.0'}

    @app.get('/api/overview')
    def overview(date: str = Query(...)):
        valid_date(date)
        db = database.read()
        day = db['days'].get(date)
        items = day['items'] if day else []
        used_starters = len(core.used_starter_ids(db))
        return {'date': date, 'exists': day is not None,
                'items': [{**item, 'full_prompt': core.story_prompt(item, 'full')} for item in items],
                'stats': metrics(items),
                'theme_names': core.THEME_NAME, 'library_size': len(db['library']),
                'ideas_remaining': remaining_ideas(db),
                'starter_used': used_starters, 'starter_total': 84,
                'days_count': len(db['days'])}

    @app.post('/api/days', status_code=201)
    def create_day(body: CreateDay):
        date = valid_date(body.date)
        with database.edit() as db:
            if date in db['days']:
                raise HTTPException(409, 'Ngày làm việc đã tồn tại.')
            ok, message = core.new_day(db, date)
            if not ok:
                raise HTTPException(409, message)
        return {'message': message, 'date': date}

    @app.get('/api/history')
    def history():
        db = database.read()
        result = []
        for date, day in sorted(db['days'].items(), reverse=True):
            items = day['items']
            result.append({'date': date, 'count': len(items),
                           'assigned': sum(x.get('status') in ('sent', 'part1', 'done') for x in items),
                           'done': sum(x.get('status') == 'done' for x in items)})
        return {'days': result, 'library_size': len(db['library']),
                'starter_used': len(core.used_starter_ids(db)), 'starter_total': 84}

    @app.post('/api/workspace/export')
    def export_workspace(body: WorkspaceExport):
        date = valid_date(body.date)
        db = database.read()
        day = db['days'].get(date)
        if day is None:
            raise HTTPException(404, 'Ngày làm việc chưa được tạo.')
        try:
            return export_lane(date, body.ai, (item for item in day['items'] if item.get('ai') == body.ai))
        except (OSError, ValueError) as exc:
            raise HTTPException(409, f'Không thể xuất file TXT: {exc}') from exc

    @app.get('/api/workspace/config')
    def get_workspace_config():
        try:
            return check_workspace()
        except (OSError, ValueError) as exc:
            raise HTTPException(409, f'Workspace không hợp lệ: {exc}') from exc

    @app.put('/api/workspace/config')
    def update_workspace_config(body: WorkspaceConfig):
        try:
            return set_workspace(body.folder)
        except (OSError, ValueError) as exc:
            raise HTTPException(422, f'Không thể cấu hình workspace: {exc}') from exc

    @app.get('/api/workspace/status')
    def workspace_status(date: str = Query(...), ai: int = Query(..., ge=1, le=3)):
        valid_date(date)
        if ai not in (1, 2, 3):
            raise HTTPException(422, 'AI lane phải là 1, 2 hoặc 3.')
        db = database.read()
        day = db['days'].get(date)
        if day is None:
            raise HTTPException(404, 'Ngày làm việc chưa được tạo.')
        try:
            return {'date': date, 'ai': ai, 'items': lane_status(date, ai, day['items'])}
        except (OSError, ValueError) as exc:
            raise HTTPException(409, f'Không thể đọc workspace: {exc}') from exc

    @app.get('/api/workspace/file')
    def workspace_file(date: str = Query(...), ai: int = Query(..., ge=1, le=3),
                       slot: int = Query(..., ge=1, le=14),
                       kind: Literal['prompt', 'output'] = Query(...)):
        valid_date(date)
        if ai not in (1, 2, 3):
            raise HTTPException(422, 'AI lane phải là 1, 2 hoặc 3.')
        db = database.read()
        day = db['days'].get(date)
        if day is None:
            raise HTTPException(404, 'Ngày làm việc chưa được tạo.')
        try:
            return read_file(date, ai, slot, kind, day['items'])
        except (OSError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.put('/api/workspace/file')
    def update_workspace_file(body: WorkspaceFile):
        valid_date(body.date)
        db = database.read()
        day = db['days'].get(body.date)
        if day is None:
            raise HTTPException(404, 'Ngày làm việc chưa được tạo.')
        try:
            return write_file(body.date, body.ai, body.slot, body.kind, body.content, body.expected_hash, day['items'])
        except FileExistsError as exc:
            raise HTTPException(409, str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.delete('/api/workspace/file')
    def remove_workspace_file(date: str = Query(...), ai: int = Query(..., ge=1, le=3),
                              slot: int = Query(..., ge=1, le=14),
                              kind: Literal['prompt', 'output'] = Query(...)):
        valid_date(date)
        if ai not in (1, 2, 3):
            raise HTTPException(422, 'AI lane phải là 1, 2 hoặc 3.')
        db = database.read()
        day = db['days'].get(date)
        if day is None:
            raise HTTPException(404, 'Ngày làm việc chưa được tạo.')
        try:
            return delete_file(date, ai, slot, kind, day['items'])
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get('/api/days/{date}/items/{uid}/prompt')
    def prompt(date: str, uid: str, mode: Literal['full', 'part1', 'part2'] = 'full'):
        valid_date(date)
        item = get_item(database.read(), date, uid)
        return {'text': core.story_prompt(item, mode), 'title': item.get('title'), 'ai': item['ai'], 'uid': uid}

    @app.post('/api/days/{date}/items/{uid}/copied')
    def copied(date: str, uid: str, body: Copied):
        valid_date(date)
        with database.edit() as db:
            item = get_item(db, date, uid)
            if item['status'] != 'done':
                item['status'] = 'part1' if body.mode == 'part1' else 'sent'
            item['last_copied'] = dt.datetime.now().isoformat(timespec='seconds')
            remaining = remaining_ideas(db)
        return {'message': 'Đã ghi nhận sao chép prompt thành công.', 'status': item['status'],
                'ideas_remaining': remaining}

    @app.post('/api/days/{date}/items/{uid}/undo-copied')
    def undo_copied(date: str, uid: str):
        valid_date(date)
        with database.edit() as db:
            item = get_item(db, date, uid)
            if item['status'] == 'done':
                raise HTTPException(409, 'Hãy hoàn tác trạng thái hoàn tất trước khi hoàn tác sao chép.')
            if item['status'] == 'ready':
                return {'message': 'Thẻ chưa được ghi nhận sao chép.', 'status': 'ready',
                        'ideas_remaining': remaining_ideas(db)}
            item['status'] = 'ready'
            item.pop('last_copied', None)
            remaining = remaining_ideas(db)
        return {'message': 'Đã hoàn tác sao chép prompt.', 'status': 'ready',
                'ideas_remaining': remaining}

    @app.post('/api/days/{date}/items/{uid}/toggle-done')
    def toggle_done(date: str, uid: str):
        valid_date(date)
        with database.edit() as db:
            item = get_item(db, date, uid)
            item['status'] = 'sent' if item['status'] == 'done' else 'done'
        return {'message': 'Đã cập nhật trạng thái.', 'status': item['status']}

    @app.patch('/api/days/{date}/items/{uid}/brief')
    def edit_brief(date: str, uid: str, body: BriefEdit):
        valid_date(date)
        edits = {k: v.strip() for k, v in body.model_dump().items()}
        if any(len(v) < 7 for v in edits.values()):
            raise HTTPException(422, 'Mỗi trường nội dung cần ít nhất 7 ký tự.')
        with database.edit() as db:
            item = get_item(db, date, uid)
            item.update(edits)
        return {'message': 'Đã lưu nội dung thẻ.', 'item': item}

    @app.get('/api/days/{date}/scan')
    def scan_day(date: str, threshold: float = Query(.28, ge=.0, le=1.0)):
        valid_date(date)
        items = get_day(database.read(), date)['items']
        pairs = []
        for i, a in enumerate(items):
            for b in items[i+1:]:
                score = core.similarity(a, b)
                if score >= threshold:
                    pairs.append({'score': score, 'first': {'slot': a['slot'], 'title': a['title']},
                                  'second': {'slot': b['slot'], 'title': b['title']}})
        pairs.sort(key=lambda x: x['score'], reverse=True)
        return {'pairs': pairs[:20], 'total': len(pairs), 'method': 'lexical-jaccard'}

    @app.post('/api/days/{date}/items/{uid}/scan')
    def scan_item(date: str, uid: str, edits: BriefEdit | None = None):
        valid_date(date)
        db = database.read()
        item = get_item(db, date, uid)
        probe = dict(item)
        if edits:
            probe.update(edits.model_dump())
        peers = [x for x in db['days'][date]['items'] + core.all_archived(db, exclude_date=date)
                 if x.get('uid') != uid]
        matches = core.unique_candidates(probe, peers, limit=5)
        return {'matches': [{'score': s, 'title': x.get('title'), 'slot': x.get('slot')} for s, x in matches],
                'method': 'lexical-jaccard'}

    @app.get('/api/planning-prompt')
    def plan_prompt(date: str, ai: int = Query(..., ge=1, le=3)):
        valid_date(date)
        return {'text': core.planning_prompt(database.read(), date, ai)}

    @app.post('/api/days/{date}/plan')
    def import_plan(date: str, body: ImportPlan):
        valid_date(date)
        try:
            batch = core.parse_planner(body.text, body.ai)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        with database.edit() as db:
            day = db['days'].get(date)
            existing = day['items'] if day else []
            old_lane = [s for s in existing if s.get('ai') == body.ai]
            if any(s.get('status') != 'ready' for s in old_lane):
                raise HTTPException(409, 'AI này đã có thẻ được giao hoặc hoàn tất; không cho phép ghi đè.')
            if old_lane and not body.replace_ready:
                raise HTTPException(409, {'code': 'replace_ready', 'message': 'Xác nhận thay thế lane có thẻ chưa giao.'})
            other_items = [s for s in existing if s.get('ai') != body.ai]
            historical = core.all_archived(db, exclude_date=date)
            alerts = []
            for i, item in enumerate(batch):
                rivals = core.unique_candidates(item, other_items + historical + batch[:i], limit=1)
                if rivals and rivals[0][0] >= .48:
                    score, other = rivals[0]
                    alerts.append({'line': i+1, 'score': score, 'title': item['title'], 'other_title': other.get('title')})
            if alerts and not body.allow_similar:
                raise HTTPException(409, {'code': 'similar_ideas', 'message': 'Phát hiện brief gần giống theo từ khóa.', 'alerts': alerts[:10]})
            if day is None:
                db['days'][date] = {'items': [], 'created': dt.datetime.now().isoformat(timespec='seconds')}
                day = db['days'][date]
            for idx, item in enumerate(batch):
                item['slot'] = (body.ai - 1) * 14 + idx + 1
                item['uid'] = __import__('uuid').uuid4().hex
                item['status'] = 'ready'
            day['items'] = sorted(other_items + batch, key=lambda s: (s['ai'], s['slot']))
            for item in batch:
                db['library'].append({k: item[k] for k in core.KEYS} | {'id': item['id'], 'source': 'imported'})
        return {'message': f'Đã nhập 14 ý tưởng cho AI {body.ai}.', 'count': len(batch), 'warnings': len(alerts)}

    @app.get('/api/backup')
    def download_backup():
        content = json.dumps(database.read(), ensure_ascii=False, indent=2).encode('utf-8')
        return Response(content, media_type='application/json; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="thangmia_backup.json"'})

    @app.post('/api/restore')
    async def restore(request: Request):
        if int(request.headers.get('content-length', '0') or '0') > 12_000_000:
            raise HTTPException(413, 'File sao lưu quá lớn.')
        payload = await request.body()
        if len(payload) > 12_000_000:
            raise HTTPException(413, 'File sao lưu quá lớn.')
        try:
            incoming = validate_backup(json.loads(payload))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(422, f'Sao lưu không hợp lệ: {exc}') from exc
        with database.edit() as db:
            db.clear()
            db.update(incoming)
        return {'message': 'Đã khôi phục toàn bộ dữ liệu từ JSON.', 'days_count': len(incoming['days'])}

    return app


app = create_app()
