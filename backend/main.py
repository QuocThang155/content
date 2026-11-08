"""THẮNG MIA API. Run: uvicorn backend.main:app --reload --port 8000"""
from __future__ import annotations
import datetime as dt
import json
import os
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import core
from .store import DEFAULT_DATABASE_PATH, Store
from .workspace import (
    check_workspace, delete_file, export_lane, export_lane_with_image_prompt, lane_status,
    read_file, read_image, set_workspace, write_file,
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


def purge_expired_archives(db):
    cutoff = dt.datetime.now() - dt.timedelta(days=2)
    removed = 0
    retired_ids = set(db.get('retired_idea_ids', []))
    for day in db['days'].values():
        kept = []
        for item in day['items']:
            archived_at = item.get('archived_at')
            if archived_at:
                try:
                    expired = dt.datetime.fromisoformat(archived_at) <= cutoff
                except ValueError:
                    expired = False
                if expired:
                    removed += 1
                    if item.get('id'):
                        retired_ids.add(item['id'])
                    continue
            kept.append(item)
        day['items'] = kept
    if removed:
        db['retired_idea_ids'] = sorted(retired_ids)
        active_ids = {item.get('id') for day in db['days'].values() for item in day['items']}
        db['library'] = [item for item in db['library'] if item.get('id') in active_ids]
    return removed


def remaining_ideas(db):
    copied = sum(
        item.get('status') in ('sent', 'part1', 'done')
        for day in db['days'].values()
        for item in day['items']
    )
    return max(0, len(db['library']) - copied)


def available_library_items(db):
    used_ids = core.archived_ids(db)
    retired_ids = set(db.get('retired_idea_ids', []))
    candidates = {brief['id']: brief for brief in core.seed_bank()}
    candidates.update({brief['id']: brief for brief in db['library']})
    return [
        {key: brief.get(key, '') for key in core.KEYS}
        | {'id': brief['id'], 'source': brief.get('source', 'imported')}
        for brief in candidates.values()
        if brief['id'] not in used_ids
        and brief['id'] not in retired_ids
        and brief.get('theme') in core.THEME_NAME
    ]


def next_workflow_date(db):
    candidate = dt.date.today()
    while candidate.isoformat() in db['days']:
        candidate += dt.timedelta(days=1)
    return candidate.isoformat()


def archive_duplicate_alerts(db, items, threshold=.28):
    archived = [
        (date, item)
        for date, day in db['days'].items()
        for item in day.get('items', [])
        if item.get('archived_at')
    ]
    alerts = []
    for item in items:
        for date, archived_item in archived:
            if item.get('id') == archived_item.get('id'):
                continue
            score = core.similarity(item, archived_item)
            if score >= threshold:
                alerts.append({
                    'item_uid': item.get('uid'),
                    'item_slot': item.get('slot'),
                    'item_title': item.get('title'),
                    'archive_date': date,
                    'archive_title': archived_item.get('title'),
                    'score': score,
                })
    alerts.sort(key=lambda alert: alert['score'], reverse=True)
    return alerts[:20]


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


class BriefMetadata(BaseModel):
    notes: str = Field(default='', max_length=10000)
    favorite: bool = False
    draft: bool = False


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
    kind: Literal['prompt', 'image_prompt', 'output']
    content: str
    expected_hash: str | None = None


class PromptTemplateBody(BaseModel):
    content: str = Field(max_length=200000)


class PromptPreview(BaseModel):
    date: str
    uid: str
    mode: Literal['full', 'part1', 'part2', 'image']
    content: str | None = Field(default=None, max_length=200000)


def create_app(store: Store | None = None) -> FastAPI:
    database = store or Store(DEFAULT_PATH)
    app = FastAPI(title='thangmia API', version='3.3.0', description='Điều phối 42 brief/ngày, không gọi API AI.')

    @app.get('/api/health')
    def health():
        return {'ok': True, 'app': 'THẮNG MIA', 'version': '3.3.0'}

    @app.get('/api/overview')
    def overview(date: str = Query(...)):
        valid_date(date)
        with database.edit() as db:
            purge_expired_archives(db)
            day = db['days'].get(date)
            items = [item for item in day['items'] if not item.get('archived_at')] if day else []
            public_items = [{**item, 'full_prompt': None,
                             'lane_slot': item['slot'] - ((item['ai'] - 1) * 14)}
                            for item in items]
            used_starters = len(core.used_starter_ids(db))
            result = {'date': date, 'exists': day is not None,
                      'items': public_items,
                      'stats': metrics(items),
                      'theme_names': core.THEME_NAME, 'library_size': len(available_library_items(db)),
                      'ideas_remaining': remaining_ideas(db),
                      'starter_used': used_starters, 'starter_total': len(core.seed_bank()),
                      'days_count': len(db['days'])}
        return result

    @app.post('/api/days', status_code=201)
    def create_day(body: CreateDay):
        date = valid_date(body.date)
        with database.edit() as db:
            purge_expired_archives(db)
            if date in db['days']:
                raise HTTPException(409, 'Ngày làm việc đã tồn tại.')
            ok, message = core.new_day(db, date)
            if not ok:
                raise HTTPException(409, message)
            warnings = archive_duplicate_alerts(db, db['days'][date]['items'])
        return {'message': message, 'date': date, 'archive_duplicates': warnings}

    @app.get('/api/history')
    def history():
        with database.edit() as db:
            purge_expired_archives(db)
        result = []
        for date, day in sorted(db['days'].items(), reverse=True):
            items = [item for item in day['items'] if not item.get('archived_at')]
            result.append({'date': date, 'count': len(items),
                           'assigned': sum(x.get('status') in ('sent', 'part1', 'done') for x in items),
                           'done': sum(x.get('status') == 'done' for x in items)})
        return {'days': result, 'library_size': len(available_library_items(db)),
                'starter_used': len(core.used_starter_ids(db)),
                'starter_total': len(core.seed_bank())}

    @app.get('/api/library')
    def idea_library():
        with database.edit() as db:
            purge_expired_archives(db)
            items = available_library_items(db)
        theme_order = {theme: index for index, (theme, _) in enumerate(core.THEMES)}
        items.sort(key=lambda brief: (theme_order[brief['theme']], brief['title'].casefold()))
        theme_counts = {theme: 0 for theme, _ in core.THEMES}
        for brief in items:
            theme_counts[brief['theme']] += 1
        return {'items': items, 'available_count': len(items),
                'theme_names': core.THEME_NAME, 'theme_counts': theme_counts,
                'starter_total': len(core.seed_bank())}

    @app.delete('/api/library')
    def clear_idea_library():
        with database.edit() as db:
            purge_expired_archives(db)
            archived_ids = {
                item['id']
                for day in db['days'].values()
                for item in day.get('items', [])
                if item.get('archived_at') and item.get('id')
            }
            retired_ids = set(db.get('retired_idea_ids', []))
            candidates = {brief['id']: brief for brief in core.seed_bank()}
            candidates.update({brief['id']: brief for brief in db['library']})
            cleared_workflow_ids = set()
            cleared_workflow_count = 0
            for day in db['days'].values():
                retained = []
                for item in day.get('items', []):
                    if item.get('archived_at'):
                        retained.append(item)
                    else:
                        cleared_workflow_count += 1
                        if item.get('id'):
                            cleared_workflow_ids.add(item['id'])
                day['items'] = retained
            retired_ids.update(set(candidates) - archived_ids)
            retired_ids.update(cleared_workflow_ids - archived_ids)
            db['retired_idea_ids'] = sorted(retired_ids)
            deleted_ids = set(candidates) - archived_ids
            db['library'] = []
            db['replenish_workflow'] = True
        return {
            'message': 'Đã xóa ý tưởng chưa dùng và các bài Workflow đang hoạt động.',
            'deleted_count': len(deleted_ids),
            'workflow_cleared_count': cleared_workflow_count,
            'days_preserved': len(db['days']),
        }

    @app.post('/api/library/import')
    def import_library_ideas(body: ImportPlan):
        try:
            batch = core.parse_planner(body.text, body.ai)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        with database.edit() as db:
            purge_expired_archives(db)
            candidates = {brief['id']: brief for brief in core.seed_bank()}
            candidates.update({brief['id']: brief for brief in db['library']})
            candidates.update({
                item['id']: item
                for day in db['days'].values()
                for item in day['items']
                if item.get('id')
            })
            existing_ideas = list(candidates.values())
            alerts = []
            for index, item in enumerate(batch):
                rivals = core.unique_candidates(item, existing_ideas + batch[:index], limit=1)
                if rivals and rivals[0][0] >= .48:
                    score, other = rivals[0]
                    alerts.append({
                        'line': index + 1,
                        'score': score,
                        'title': item['title'],
                        'other_title': other.get('title'),
                    })
            if alerts and not body.allow_similar:
                raise HTTPException(409, {
                    'code': 'similar_ideas',
                    'message': 'Phát hiện brief gần giống theo từ khóa.',
                    'alerts': alerts[:10],
                })
            for item in batch:
                db['library'].append(
                    {key: item[key] for key in core.KEYS}
                    | {'id': item['id'], 'source': 'imported'}
                )
            library_size = len(batch)
            workflow_date = None
            workflow_warnings = []
            if db.get('replenish_workflow'):
                workflow_date = next_workflow_date(db)
                ok, _ = core.new_day(db, workflow_date)
                if ok:
                    workflow_warnings = archive_duplicate_alerts(
                        db, db['days'][workflow_date]['items']
                    )
                    db['replenish_workflow'] = False
                else:
                    workflow_date = None
        return {
            'message': f'Đã nạp {library_size} ý tưởng mới vào kho.',
            'count': library_size,
            'workflow_date': workflow_date,
            'archive_duplicates': workflow_warnings,
        }

    @app.post('/api/library/reset')
    def reset_idea_library():
        with database.edit() as db:
            purge_expired_archives(db)
            used_ids = core.archived_ids(db)
            retired_ids = set(db.get('retired_idea_ids', []))
            available_by_theme = {theme: [] for theme, _ in core.THEMES}
            candidates = {brief['id']: brief for brief in core.seed_bank()}
            candidates.update({brief['id']: brief for brief in db['library']})
            for brief in candidates.values():
                if (brief['id'] not in used_ids and brief['id'] not in retired_ids
                        and brief.get('theme') in available_by_theme):
                    available_by_theme[brief['theme']].append(brief)

            missing = [
                f'{core.THEME_NAME[theme]}: còn {len(available)} / 3'
                for theme, available in available_by_theme.items()
                if len(available) < 3
            ]
            if missing:
                raise HTTPException(
                    409,
                    'Không thể tạo kho mới gồm 42 ý tưởng chưa dùng; '
                    'một số chủ đề đã hết mẫu: ' + '; '.join(missing),
                )

            db['library'] = [
                brief
                for theme, _ in core.THEMES
                for brief in available_by_theme[theme][:3]
            ]
            library_size = len(db['library'])
        return {'message': 'Đã tạo kho mới gồm 42 ý tưởng chưa dùng.',
                'library_size': library_size, 'added': library_size,
                'starter_total': len(core.seed_bank())}

    @app.post('/api/workspace/export')
    def export_workspace(body: WorkspaceExport):
        date = valid_date(body.date)
        db = database.read()
        day = db['days'].get(date)
        if day is None:
            raise HTTPException(404, 'Ngày làm việc chưa được tạo.')
        try:
            return export_lane(date, body.ai, (item for item in day['items']
                                               if item.get('ai') == body.ai and not item.get('archived_at')),
                               db.get('prompt_templates', {}))
        except (OSError, ValueError) as exc:
            raise HTTPException(409, f'Không thể xuất file TXT: {exc}') from exc

    @app.post('/api/workspace/export-with-image')
    def export_workspace_with_image(body: WorkspaceExport):
        date = valid_date(body.date)
        db = database.read()
        day = db['days'].get(date)
        if day is None:
            raise HTTPException(404, 'Ngày làm việc chưa được tạo.')
        try:
            return export_lane_with_image_prompt(date, body.ai,
                (item for item in day['items']
                 if item.get('ai') == body.ai and not item.get('archived_at')),
                db.get('prompt_templates', {}))
        except (OSError, ValueError) as exc:
            raise HTTPException(409, f'Không thể xuất prompt: {exc}') from exc

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

    @app.get('/api/prompt-templates')
    def get_prompt_templates():
        db = database.read()
        return {'templates': db.get('prompt_templates', {'full': '', 'part1': '', 'part2': '', 'image': ''}),
                'variables': list(core.PROMPT_VARIABLES),
                'modes': list(core.PROMPT_MODES)}

    @app.put('/api/prompt-templates/{mode}')
    def save_prompt_template(mode: Literal['full', 'part1', 'part2', 'image'], body: PromptTemplateBody):
        try:
            content = core.validate_prompt_template(body.content)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        with database.edit() as db:
            db.setdefault('prompt_templates', {})[mode] = content
        return {'mode': mode, 'content': content}

    @app.delete('/api/prompt-templates/{mode}')
    def delete_prompt_template(mode: Literal['full', 'part1', 'part2', 'image']):
        with database.edit() as db:
            db.setdefault('prompt_templates', {})[mode] = ''
        return {'mode': mode, 'content': ''}

    @app.post('/api/prompt-templates/preview')
    def preview_prompt(body: PromptPreview):
        valid_date(body.date)
        db = database.read()
        item = get_item(db, body.date, body.uid)
        templates = dict(db.get('prompt_templates', {}))
        if body.content is not None:
            try:
                templates[body.mode] = core.validate_prompt_template(body.content)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        try:
            text = core.render_prompt(item, body.mode, templates)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {'text': text, 'mode': body.mode, 'uid': body.uid}

    @app.get('/api/workspace/image')
    def workspace_image(date: str = Query(...), ai: int = Query(..., ge=1, le=3),
                        slot: int = Query(..., ge=1, le=14)):
        valid_date(date)
        if ai not in (1, 2, 3):
            raise HTTPException(422, 'AI lane phải là 1, 2 hoặc 3.')
        db = database.read()
        day = db['days'].get(date)
        if day is None:
            raise HTTPException(404, 'Ngày làm việc chưa được tạo.')
        try:
            content, media_type, filename = read_image(date, ai, slot, day['items'])
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc
        return Response(content, media_type=media_type,
                        headers={'Content-Disposition': f'inline; filename="{filename}"'})

    @app.get('/api/workspace/file')
    def workspace_file(date: str = Query(...), ai: int = Query(..., ge=1, le=3),
                       slot: int = Query(..., ge=1, le=14),
                       kind: Literal['prompt', 'image_prompt', 'output'] = Query(...)):
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
                              kind: Literal['prompt', 'image_prompt', 'output'] = Query(...)):
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
        db = database.read()
        item = get_item(db, date, uid)
        try:
            text = core.render_prompt(item, mode, db.get('prompt_templates', {}))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {'text': text, 'title': item.get('title'), 'ai': item['ai'], 'uid': uid}

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

    @app.post('/api/days/{date}/items/{uid}/output-copied')
    def output_copied(date: str, uid: str):
        valid_date(date)
        with database.edit() as db:
            item = get_item(db, date, uid)
            local_slot = item['slot'] - ((item['ai'] - 1) * 14)
            try:
                output = read_file(date, item['ai'], local_slot, 'output', get_day(db, date)['items'])
            except (OSError, ValueError) as exc:
                raise HTTPException(409, str(exc)) from exc
            if not output['exists']:
                raise HTTPException(409, 'Chưa có truyện trả về để sao chép.')
            item['status'] = 'done'
            item['last_copied'] = dt.datetime.now().isoformat(timespec='seconds')
            remaining = remaining_ideas(db)
        return {'message': 'Đã sao chép truyện trả về và ghi nhận hoàn tất.',
                'status': item['status'], 'ideas_remaining': remaining}

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

    @app.post('/api/days/{date}/items/{uid}/archive')
    def archive_item(date: str, uid: str):
        valid_date(date)
        with database.edit() as db:
            purge_expired_archives(db)
            item = get_item(db, date, uid)
            if item.get('status') != 'done':
                raise HTTPException(409, 'Chỉ có thể lưu trữ bài đã hoàn tất.')
            item['archived_at'] = dt.datetime.now().isoformat(timespec='seconds')
        return {'message': 'Đã chuyển bài vào Kho lưu trữ.', 'archived_at': item['archived_at']}

    @app.get('/api/archive')
    def archive():
        with database.edit() as db:
            purge_expired_archives(db)
            items = []
            for date, day in db['days'].items():
                items.extend({**item, 'date': date} for item in day['items'] if item.get('archived_at'))
        return {'items': items}

    @app.delete('/api/days/{date}/items/{uid}')
    def delete_day_item(date: str, uid: str):
        valid_date(date)
        with database.edit() as db:
            day = get_day(db, date)
            item = get_item(db, date, uid)
            if item['status'] != 'ready':
                raise HTTPException(409, 'Chỉ có thể xóa bài chưa giao.')

            used_ids = core.archived_ids(db)
            retired_ids = set(db.get('retired_idea_ids', []))
            available = {
                brief['id']: brief
                for brief in core.seed_bank()
                if brief['id'] not in used_ids
                and brief['id'] not in retired_ids
                and brief['theme'] == item['theme']
            }
            available.update({
                brief['id']: brief
                for brief in db['library']
                if brief.get('id') not in used_ids
                and brief.get('id') not in retired_ids
                and brief.get('theme') == item['theme']
            })
            replacement_brief = next(iter(available.values()), None)
            if replacement_brief is None:
                raise HTTPException(
                    409,
                    f'Không còn ý tưởng chưa dùng thuộc chủ đề {core.THEME_NAME.get(item["theme"], item["theme"])} '
                    'để bù vào slot này. Hãy bổ sung ý tưởng mới trước khi xóa.',
                )

            replacement = dict(replacement_brief)
            replacement.update({
                'uid': str(uuid.uuid4()),
                'ai': item['ai'],
                'slot': item['slot'],
                'status': 'ready',
                'notes': '',
                'favorite': False,
                'draft': False,
            })
            if not any(brief.get('id') == replacement['id'] for brief in db['library']):
                db['library'].append({key: replacement[key] for key in core.KEYS}
                                     | {'id': replacement['id'], 'source': replacement.get('source', 'starter')})
            db.setdefault('retired_idea_ids', []).append(item['id'])
            day['items'] = [
                replacement if candidate.get('uid') == uid else candidate
                for candidate in day['items']
            ]
            db['library'] = [brief for brief in db['library'] if brief.get('id') != item.get('id')]
            remaining = remaining_ideas(db)
        return {'message': 'Đã xóa bài và bổ sung ý tưởng mới vào đúng slot.',
                'item': replacement, 'ideas_remaining': remaining}

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

    @app.patch('/api/days/{date}/items/{uid}/metadata')
    def edit_metadata(date: str, uid: str, body: BriefMetadata):
        valid_date(date)
        with database.edit() as db:
            item = get_item(db, date, uid)
            item.update({key: value.strip() if isinstance(value, str) else value
                         for key, value in body.model_dump().items()})
            return {'message': 'Đã lưu metadata brief.', 'item': item}

    @app.get('/api/days/{date}/scan')
    def scan_day(date: str, threshold: float = Query(.28, ge=.0, le=1.0)):
        valid_date(date)
        with database.edit() as db:
            purge_expired_archives(db)
        items = [
            item for item in get_day(db, date)['items']
            if not item.get('archived_at')
        ]
        pairs = []
        for i, a in enumerate(items):
            for b in items[i+1:]:
                score = core.similarity(a, b)
                if score >= threshold:
                    pairs.append({'score': score, 'first': {'slot': a['slot'], 'title': a['title']},
                                  'second': {'slot': b['slot'], 'title': b['title']}})
        archived = [
            (archived_date, item)
            for archived_date, day in db['days'].items()
            for item in day.get('items', [])
            if item.get('archived_at')
        ]
        for item in items:
            for archived_date, archived_item in archived:
                if item.get('id') == archived_item.get('id'):
                    continue
                score = core.similarity(item, archived_item)
                if score >= threshold:
                    pairs.append({
                        'score': score,
                        'first': {'slot': item['slot'], 'title': item['title']},
                        'second': {
                            'slot': archived_item['slot'],
                            'title': archived_item['title'],
                            'archived': True,
                            'date': archived_date,
                        },
                    })
        pairs.sort(
            key=lambda pair: (
                bool(pair['second'].get('archived')),
                pair['score'],
            ),
            reverse=True,
        )
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
