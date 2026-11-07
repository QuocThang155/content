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
        item = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
        base = f'/api/days/{self.date}/items/{item["uid"]}'
        prompt = self.client.get(base + '/prompt?mode=full').json()['text']
        self.assertIn('Taglish', prompt)
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
        self.assertEqual(self.client.get(base+'/prompt?mode=part2').status_code, 200)
        self.assertEqual(self.client.post(base+'/scan', json=edits).status_code, 200)
        self.assertEqual(self.client.get(f'/api/days/{self.date}/scan').status_code, 200)
        self.assertEqual(self.client.patch(base+'/brief', json={**edits,'ending':'short'}).status_code, 422)

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
