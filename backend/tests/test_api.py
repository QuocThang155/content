from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import core
from backend.main import create_app
from backend.store import Store, migrate_legacy_database


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.dir.name) / 'thangmia.sqlite3')
        self.client = TestClient(create_app(self.store))
        self.date = '2026-11-07'

    def tearDown(self):
        self.client.close()
        self.dir.cleanup()

    def create(self, date=None):
        return self.client.post('/api/days', json={'date': date or self.date})

    @staticmethod
    def planner_lines():
        return '\n'.join(
            f'{n:02} || New original title {n} || A thoughtful school volunteer {n} || A biased committee member {n} || '
            f'A committee secretly blocks fair access {n} || A written permission log {n} || '
            f'An independent review restores fair access {n} || Everyone establishes transparent rules {n}'
            for n in range(1, 15)
        )

    def test_seed_assignment_no_reuse(self):
        self.assertEqual(len(self.store.read()['library']), 84)
        ids = set()
        for date in (self.date, '2026-11-08'):
            response = self.create(date)
            self.assertEqual(response.status_code, 201, response.text)
            overview = self.client.get('/api/overview', params={'date': date}).json()
            self.assertEqual(overview['stats']['total'], 42)
            for ai in (1,2,3):
                self.assertEqual(sum(x['ai'] == ai for x in overview['items']), 14)
            for theme, _ in core.THEMES:
                self.assertEqual(sum(x['theme'] == theme for x in overview['items']), 3)
            current = {x['id'] for x in overview['items']}
            self.assertFalse(current & ids)
            ids.update(current)
        self.assertEqual(len(ids), 84)
        self.assertEqual(self.create('2026-11-09').status_code, 409)
        self.assertEqual(self.create(self.date).status_code, 409)

    def test_prompt_status_and_edit(self):
        self.create()
        self.assertEqual(self.client.put('/api/prompt-templates/full',
            json={'content': 'FULL {{title}} / {{hero}} / {{evidence}}'}).status_code, 200)
        item = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
        base = f'/api/days/{self.date}/items/{item["uid"]}'
        prompt = self.client.get(base + '/prompt?mode=full').json()['text']
        self.assertTrue(prompt.startswith('FULL '))
        self.assertIn(item['title'], prompt)
        self.assertEqual(self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]['status'], 'ready')
        self.assertEqual(self.client.post(base+'/copied', json={'mode':'part1'}).json()['status'], 'part1')
        self.assertEqual(self.client.get('/api/overview', params={'date': self.date}).json()['stats']['in_progress'], 1)
        self.assertEqual(self.client.post(base+'/copied', json={'mode':'part2'}).json()['status'], 'sent')
        self.assertEqual(self.client.get('/api/overview', params={'date': self.date}).json()['stats']['in_progress'], 1)
        undone = self.client.post(base+'/undo-copied')
        self.assertEqual(undone.status_code, 200)
        self.assertEqual(undone.json()['status'], 'ready')
        self.assertEqual(self.client.get('/api/overview', params={'date': self.date}).json()['stats']['in_progress'], 0)
        self.assertEqual(self.client.post(base+'/undo-copied').json()['status'], 'ready')
        self.client.post(base+'/copied', json={'mode':'full'})
        self.assertEqual(self.client.post(base+'/toggle-done').json()['status'], 'done')
        self.assertEqual(self.client.post(base+'/copied', json={'mode':'full'}).json()['status'], 'done')
        self.assertEqual(self.client.post(base+'/undo-copied').status_code, 409)
        self.assertEqual(self.client.post(base+'/toggle-done').json()['status'], 'sent')
        edits = {key: 'Rewritten ' + key + ' with additional context' for key, _ in core.FIELDS}
        self.assertEqual(self.client.patch(base+'/brief', json=edits).status_code, 200)
        prompt = self.client.get(base+'/prompt?mode=full').json()['text']
        self.assertIn(edits['evidence'], prompt)
        self.client.put('/api/prompt-templates/part2', json={'content': 'PART2 {{ending}}'})
        self.assertEqual(self.client.get(base+'/prompt?mode=part2').status_code, 200)
        self.assertEqual(self.client.post(base+'/scan', json=edits).status_code, 200)
        self.assertEqual(self.client.get(f'/api/days/{self.date}/scan').status_code, 200)
        self.assertEqual(self.client.patch(base+'/brief', json={**edits,'ending':'short'}).status_code, 422)

    def test_idea_vault_metadata_persists_without_changing_brief_or_status(self):
        self.create()
        item = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
        base = f'/api/days/{self.date}/items/{item["uid"]}'
        response = self.client.patch(base + '/metadata', json={
            'notes': 'Theo doi bang chung', 'favorite': True, 'draft': True,
        })
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()['item']
        self.assertEqual(saved['notes'], 'Theo doi bang chung')
        self.assertTrue(saved['favorite'])
        self.assertTrue(saved['draft'])
        self.assertEqual(saved['status'], 'ready')
        reloaded = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
        self.assertEqual(reloaded['title'], item['title'])
        self.assertEqual(reloaded['notes'], 'Theo doi bang chung')
        self.assertTrue(reloaded['favorite'])
        self.assertTrue(reloaded['draft'])

    def test_planning_parse_import_and_protect_lane(self):
        self.create()
        url = f'/api/days/{self.date}/plan'
        initial = self.client.get('/api/overview', params={'date': self.date}).json()['items']
        self.assertEqual(self.client.post(url, json={'ai':1,'text':'\n'.join(self.planner_lines().splitlines()[:13]),'replace_ready':True}).status_code, 422)
        self.assertEqual(self.client.post(url, json={'ai':1,'text':self.planner_lines()}).status_code, 409)
        warned = self.client.post(url, json={'ai':1,'text':self.planner_lines(), 'replace_ready':True})
        self.assertEqual(warned.status_code, 409)
        self.assertEqual(warned.json()['detail']['code'], 'similar_ideas')
        imported = self.client.post(url, json={'ai':1,'text':self.planner_lines(), 'replace_ready':True, 'allow_similar':True})
        self.assertEqual(imported.status_code, 200, imported.text)
        changed = self.client.get('/api/overview', params={'date': self.date}).json()['items']
        self.assertEqual(len(changed), 42)
        self.assertEqual({i['uid'] for i in changed if i['ai'] in (2,3)}, {i['uid'] for i in initial if i['ai'] in (2,3)})
        self.assertTrue(all(i['id'].startswith('CUSTOM-') for i in changed if i['ai'] == 1))
        one = next(i for i in changed if i['ai']==1)
        self.client.post(f'/api/days/{self.date}/items/{one["uid"]}/copied', json={'mode':'full'})
        self.assertEqual(self.client.post(url, json={'ai':1,'text':self.planner_lines(),'replace_ready':True}).status_code, 409)
        self.assertEqual(self.client.get('/api/history').status_code, 200)
        self.assertIn('14', self.client.get('/api/planning-prompt',params={'date':self.date,'ai':1}).json()['text'])

    def test_new_day_import_after_exhaust(self):
        self.create()
        self.create('2026-11-08')
        new_date = '2026-11-09'
        self.assertEqual(self.create(new_date).status_code, 409)
        for ai in (1,2,3):
            r = self.client.post(f'/api/days/{new_date}/plan', json={'ai':ai,'text':self.planner_lines(), 'allow_similar':True})
            self.assertEqual(r.status_code, 200, r.text)
        current = self.client.get('/api/overview',params={'date':new_date}).json()['items']
        self.assertEqual(len(current), 42)
        self.assertEqual(len({i['id'] for i in current}), 42)

    def test_backup_csv_and_restore(self):
        self.create()
        json_data = self.client.get('/api/backup').json()
        self.assertEqual(json_data['version'], 2)
        csv_response = self.client.get(f'/api/days/{self.date}/export.csv')
        self.assertEqual(csv_response.status_code, 404)
        before = self.client.get('/api/overview',params={'date':self.date}).json()
        bad = self.client.post('/api/restore',json={'version':2,'library':[],'days':{'bad-date':{'items':[]}}})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.client.get('/api/overview',params={'date':self.date}).json()['stats'],before['stats'])
        self.assertEqual(self.client.post('/api/restore',json=json_data).status_code, 200)
        self.assertEqual(self.client.get('/api/overview',params={'date':self.date}).json()['stats'],before['stats'])
        self.assertEqual(self.client.get('/api/health').json()['ok'], True)

    def test_workspace_export_writes_full_prompts_without_changing_status(self):
        self.create()
        self.client.put('/api/prompt-templates/full', json={'content': 'EXPORT {{title}} {{ending}}'})
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            'os.environ', {'THANGMIA_WORKSPACE_DIR': directory}
        ):
            response = self.client.post('/api/workspace/export', json={'date': self.date, 'ai': 1})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['written'], 14)
            files = sorted((Path(directory) / 'AI1').glob('*.txt'))
            self.assertEqual(len(files), 14)
            self.assertTrue(files[0].name.endswith('_01.txt'))
            item = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
            self.assertEqual(files[0].read_text(encoding='utf-8'), f'EXPORT {item["title"]} {item["ending"]}')
            self.assertEqual(item['status'], 'ready')
            second = self.client.post('/api/workspace/export', json={'date': self.date, 'ai': 1})
            self.assertEqual(second.json()['written'], 0)
            self.assertEqual(second.json()['skipped'], 14)

    def test_workspace_export_keeps_ai2_and_ai3_in_their_own_lanes(self):
        self.create()
        self.client.put('/api/prompt-templates/full', json={'content': 'AI {{title}}'})
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            'os.environ', {'THANGMIA_WORKSPACE_DIR': directory}
        ):
            for ai in (2, 3):
                response = self.client.post('/api/workspace/export', json={'date': self.date, 'ai': ai})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['written'], 14)
                lane = Path(directory) / f'AI{ai}'
                self.assertEqual(len(list(lane.glob(f'{self.date}_AI{ai}_??.txt'))), 14)
                self.assertFalse(list((Path(directory) / f'AI{3 if ai == 2 else 2}').glob(
                    f'{self.date}_AI{ai}_*.txt'
                )))
            for ai in (2, 3):
                status = self.client.get('/api/workspace/status', params={
                    'date': self.date, 'ai': ai
                })
                self.assertEqual(status.status_code, 200)
                self.assertEqual([item['slot'] for item in status.json()['items']], list(range(1, 15)))

    def test_workspace_files_are_mapped_editable_and_deletable(self):
        self.create()
        self.client.put('/api/prompt-templates/full', json={'content': 'EXPORT {{title}}'})
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            'os.environ', {'THANGMIA_WORKSPACE_DIR': directory}
        ):
            self.assertEqual(self.client.post('/api/workspace/export', json={'date': self.date, 'ai': 1}).status_code, 200)
            status = self.client.get('/api/workspace/status', params={'date': self.date, 'ai': 1}).json()
            first = status['items'][0]
            self.assertTrue(first['prompt_exists'])
            prompt = self.client.get('/api/workspace/file', params={
                'date': self.date, 'ai': 1, 'slot': 1, 'kind': 'prompt'
            }).json()
            changed = prompt['content'] + '\nEdited'
            saved = self.client.put('/api/workspace/file', json={
                'date': self.date, 'ai': 1, 'slot': 1, 'kind': 'prompt',
                'content': changed, 'expected_hash': prompt['hash'],
            })
            self.assertEqual(saved.status_code, 200, saved.text)
            conflict = self.client.put('/api/workspace/file', json={
                'date': self.date, 'ai': 1, 'slot': 1, 'kind': 'prompt',
                'content': 'stale', 'expected_hash': prompt['hash'],
            })
            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(self.client.delete('/api/workspace/file', params={
                'date': self.date, 'ai': 1, 'slot': 1, 'kind': 'prompt'
            }).status_code, 200)
            self.assertEqual(self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]['status'], 'ready')

    def test_export_with_image_creates_two_prompt_files_and_reads_image(self):
        self.create()
        self.client.put('/api/prompt-templates/full', json={'content': 'FULL {{title}}'})
        self.client.put('/api/prompt-templates/image', json={'content': 'IMAGE {{title}}'})
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            'os.environ', {'THANGMIA_WORKSPACE_DIR': directory}
        ):
            response = self.client.post('/api/workspace/export-with-image',
                                        json={'date': self.date, 'ai': 1})
            self.assertEqual(response.status_code, 200, response.text)
            lane = Path(directory) / 'AI1'
            self.assertEqual(len(list(lane.glob(f'{self.date}_AI1_??.txt'))), 14)
            self.assertEqual(len(list(lane.glob(f'{self.date}_AI1_??_image_prompt.txt'))), 14)
            image = lane / f'{self.date}_AI1_01_image.png'
            image.write_bytes(b'\x89PNG\r\n\x1a\n' + b'valid')
            status = self.client.get('/api/workspace/status',
                                     params={'date': self.date, 'ai': 1}).json()['items'][0]
            self.assertTrue(status['image_exists'])
            image_response = self.client.get('/api/workspace/image',
                                              params={'date': self.date, 'ai': 1, 'slot': 1})
            self.assertEqual(image_response.status_code, 200)
            self.assertEqual(image_response.headers['content-type'], 'image/png')

    def test_missing_output_returns_status_not_server_error(self):
        self.create()
        self.client.put('/api/prompt-templates/full', json={'content': 'EXPORT {{title}}'})
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            'os.environ', {'THANGMIA_WORKSPACE_DIR': directory}
        ):
            self.assertEqual(self.client.post('/api/workspace/export', json={'date': self.date, 'ai': 1}).status_code, 200)
            response = self.client.get('/api/workspace/file', params={
                'date': self.date, 'ai': 1, 'slot': 1, 'kind': 'output'
            })
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()['exists'])

    def test_missing_prompt_before_export_returns_status_not_conflict(self):
        self.create()
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            'os.environ', {'THANGMIA_WORKSPACE_DIR': directory}
        ):
            response = self.client.get('/api/workspace/file', params={
                'date': self.date, 'ai': 1, 'slot': 1, 'kind': 'prompt'
            })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['exists'])

    def test_copy_returned_output_marks_story_done(self):
        self.create()
        item = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
        base = f'/api/days/{self.date}/items/{item["uid"]}'
        self.client.put('/api/prompt-templates/full', json={'content': '{{title}}'})
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            'os.environ', {'THANGMIA_WORKSPACE_DIR': directory}
        ):
            self.assertEqual(self.client.post('/api/workspace/export',
                json={'date': self.date, 'ai': item['ai']}).status_code, 200)
            output = Path(directory) / 'AI1' / f'{self.date}_AI1_01_output.txt'
            output.write_text('Returned story', encoding='utf-8')
            response = self.client.post(base + '/output-copied')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'done')
            self.assertEqual(self.client.post(base + '/output-copied').json()['status'], 'done')

    def test_done_is_retained_and_ready_item_can_be_deleted(self):
        self.create()
        item = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
        base = f'/api/days/{self.date}/items/{item["uid"]}'
        self.assertEqual(self.client.delete(base).status_code, 200)
        overview = self.client.get('/api/overview', params={'date': self.date}).json()
        self.assertFalse(any(candidate['uid'] == item['uid'] for candidate in overview['items']))
        self.assertEqual(self.client.delete(base).status_code, 404)
        remaining = self.client.get('/api/overview', params={'date': self.date}).json()['ideas_remaining']
        self.assertEqual(remaining, 83)

    def test_done_item_can_be_archived_and_expires_after_two_days(self):
        self.create()
        item = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
        base = f'/api/days/{self.date}/items/{item["uid"]}'
        self.client.post(base + '/copied', json={'mode': 'full'})
        self.assertEqual(self.client.post(base + '/toggle-done').json()['status'], 'done')
        archived = self.client.post(base + '/archive')
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(len(self.client.get('/api/archive').json()['items']), 1)
        self.assertEqual(self.client.get('/api/overview', params={'date': self.date}).json()['stats']['total'], 41)
        with self.store.edit() as db:
            db['days'][self.date]['items'][0]['archived_at'] = '2020-01-01T00:00:00'
        self.assertEqual(self.client.get('/api/archive').json()['items'], [])

    def test_workspace_config_rejects_relative_path(self):
        response = self.client.put('/api/workspace/config', json={'folder': 'relative\\workspace'})
        self.assertEqual(response.status_code, 422)

    def test_prompt_templates_are_empty_and_validate_render_preview(self):
        self.assertEqual(self.client.get('/api/prompt-templates').json()['templates'],
                         {'full': '', 'part1': '', 'part2': '', 'image': ''})
        self.create()
        item = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
        self.assertEqual(self.client.get(f'/api/days/{self.date}/items/{item["uid"]}/prompt').status_code, 409)
        self.assertEqual(self.client.post('/api/workspace/export', json={'date': self.date, 'ai': 1}).status_code, 409)
        saved = self.client.put('/api/prompt-templates/full', json={
            'content': '{{title}}|{{title}}|{{hero}}'
        })
        self.assertEqual(saved.status_code, 200)
        preview = self.client.post('/api/prompt-templates/preview', json={
            'date': self.date, 'uid': item['uid'], 'mode': 'full',
            'content': 'Preview {{ending}}'
        })
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()['text'], f'Preview {item["ending"]}')
        self.assertEqual(self.client.put('/api/prompt-templates/part1',
            json={'content': 'P1 {{title}}'}).status_code, 200)
        self.assertEqual(self.client.put('/api/prompt-templates/part2',
            json={'content': 'P2 {{title}}'}).status_code, 200)
        invalid = self.client.put('/api/prompt-templates/full',
            json={'content': '{{unknown}}'})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(self.client.delete('/api/prompt-templates/full').status_code, 200)
        self.assertEqual(self.client.get(f'/api/days/{self.date}/items/{item["uid"]}/prompt').status_code, 409)


class DatabaseMigrationTests(unittest.TestCase):
    def test_legacy_database_is_backed_up_and_copied_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / 'legacy' / 'story42.sqlite3'
            target = root / 'new' / 'thangmia.sqlite3'
            Store(legacy)
            with patch('backend.store.LEGACY_DATABASE_PATH', legacy), patch(
                'backend.store.DEFAULT_DATABASE_PATH', target
            ):
                migrate_legacy_database(target)
                self.assertTrue(target.exists())
                backups = list(legacy.parent.glob('story42.sqlite3.migration-backup-*'))
                self.assertEqual(len(backups), 1)
                self.assertEqual(target.read_bytes(), legacy.read_bytes())

                target.write_bytes(b'new database')
                migrate_legacy_database(target)
                self.assertEqual(target.read_bytes(), b'new database')


if __name__ == '__main__':
    unittest.main()
