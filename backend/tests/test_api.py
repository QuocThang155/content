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

    def test_health_reports_release_version(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['version'], '3.3.0')

    @staticmethod
    def planner_lines():
        return '\n'.join(
            f'{n:02} || New original title {n} || A thoughtful school volunteer {n} || A biased committee member {n} || '
            f'A committee secretly blocks fair access {n} || A written permission log {n} || '
            f'An independent review restores fair access {n} || Everyone establishes transparent rules {n}'
            for n in range(1, 15)
        )

    def test_similarity_detects_paraphrases_but_not_shared_setting_alone(self):
        original = {
            'title': 'The Missing Payroll Ledger',
            'hero': 'A junior payroll clerk',
            'antagonist': 'The office manager',
            'conflict': 'The manager hid the signed payroll sheets and blamed the clerk for missing wages',
            'evidence': 'A dated payroll folder and bank transfer records',
            'reversal': 'An audit showed the manager moved the sheets to conceal an unauthorized deduction',
            'ending': 'The clerk was cleared and payroll controls were repaired',
        }
        paraphrase = {
            'title': 'The Hidden Wage Records',
            'hero': 'A junior payroll assistant',
            'antagonist': 'The office supervisor',
            'conflict': 'The supervisor concealed signed wage records then accused the assistant of losing pay documents',
            'evidence': 'Timestamped payroll files and bank payment records',
            'reversal': 'An audit proved the supervisor relocated the files to hide an improper deduction',
            'ending': 'The assistant was cleared and the payroll review process was fixed',
        }
        same_setting_different_plot = {
            'title': 'The Night Garden Map',
            'hero': 'A junior payroll clerk',
            'antagonist': 'The office manager',
            'conflict': 'The manager assigned a garden plot to another volunteer without following the rotation',
            'evidence': 'A planting calendar and shared gate log',
            'reversal': 'The board found the manager changed the schedule after approval',
            'ending': 'The volunteer rota was restored',
        }

        self.assertGreaterEqual(core.similarity(original, paraphrase), .48)
        self.assertLess(core.similarity(original, same_setting_different_plot), .28)

    def test_seed_assignment_no_reuse(self):
        self.assertEqual(len(self.store.read()['library']), 126)
        ids = set()
        for date in (self.date, '2026-11-08', '2026-11-09'):
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
        self.assertEqual(len(ids), 126)
        self.assertEqual(self.create('2026-11-10').status_code, 409)
        self.assertEqual(self.create(self.date).status_code, 409)

    def test_current_idea_library_shows_available_and_workflow_ideas(self):
        response = self.client.get('/api/library')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['available_count'], 126)

        self.create()
        assigned_ids = core.archived_ids(self.store.read())
        response = self.client.get('/api/library')

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['available_count'], 84)
        self.assertEqual(response.json()['workflow_count'], 42)
        self.assertEqual(response.json()['total_count'], 126)
        visible = {item['id']: item for item in response.json()['items']}
        self.assertTrue(assigned_ids.issubset(visible))
        self.assertTrue(all(visible[idea_id]['in_workflow'] for idea_id in assigned_ids))
        self.assertEqual(
            {visible[idea_id]['workflow_status'] for idea_id in assigned_ids},
            {'ready'},
        )
        self.assertEqual(
            self.client.get('/api/overview', params={'date': self.date}).json()['library_size'],
            84,
        )
        self.assertEqual(self.client.get('/api/history').json()['library_size'], 84)
        self.assertEqual(set(response.json()['theme_counts']), {theme for theme, _ in core.THEMES})

    def test_imported_ideas_are_saved_to_library_and_workflow_together(self):
        self.assertEqual(self.create().status_code, 201)
        original = self.client.get('/api/overview', params={'date': self.date}).json()
        payload = {
            'ai': 1,
            'text': self.planner_lines(),
            'replace_ready': True,
            'allow_similar': True,
        }

        imported = self.client.post(f'/api/days/{self.date}/plan', json=payload)

        self.assertEqual(imported.status_code, 200, imported.text)
        workflow = self.client.get('/api/overview', params={'date': self.date}).json()
        workflow_items = [item for item in workflow['items'] if item['ai'] == 1]
        self.assertEqual(len(workflow_items), 14)
        self.assertTrue(all(item['id'].startswith('CUSTOM-') for item in workflow_items))
        self.assertEqual(imported.json()['count'], 14)

        library = self.client.get('/api/library').json()
        library_items = {item['id']: item for item in library['items']}
        for item in workflow_items:
            current_idea = library_items[item['id']]
            self.assertTrue(current_idea['in_workflow'])
            self.assertEqual(current_idea['workflow_date'], self.date)
            self.assertEqual(current_idea['workflow_ai'], 1)
            self.assertEqual(current_idea['workflow_slot'], item['slot'])
            self.assertEqual(current_idea['workflow_status'], item['status'])
        self.assertEqual(library['workflow_count'], 42)
        self.assertEqual(library['total_count'], len(library['items']))
        self.assertEqual(workflow['stats']['total'], original['stats']['total'])

    def test_import_replaces_ready_lane_without_overwriting_archived_story(self):
        self.assertEqual(self.create().status_code, 201)
        original = self.client.get('/api/overview', params={'date': self.date}).json()
        archived_story = next(item for item in original['items'] if item['ai'] == 1)
        archive_url = f'/api/days/{self.date}/items/{archived_story["uid"]}'
        self.assertEqual(
            self.client.post(archive_url + '/copied', json={'mode': 'full'}).status_code,
            200,
        )
        self.assertEqual(self.client.post(archive_url + '/toggle-done').status_code, 200)
        self.assertEqual(self.client.post(archive_url + '/archive').status_code, 200)
        self.assertEqual(
            len([item for item in self.client.get('/api/overview', params={'date': self.date}).json()['items']
                 if item['ai'] == 1]),
            13,
        )

        imported = self.client.post(f'/api/days/{self.date}/plan', json={
            'ai': 1,
            'text': self.planner_lines(),
            'replace_ready': True,
            'allow_similar': True,
        })

        self.assertEqual(imported.status_code, 200, imported.text)
        current_items = self.client.get('/api/overview', params={'date': self.date}).json()['items']
        self.assertEqual(len([item for item in current_items if item['ai'] == 1]), 14)
        archived_items = self.client.get('/api/archive').json()['items']
        self.assertTrue(any(item['uid'] == archived_story['uid'] for item in archived_items))
        stored_day = self.store.read()['days'][self.date]['items']
        self.assertTrue(any(
            item['uid'] == archived_story['uid'] and item.get('archived_at')
            for item in stored_day
        ))

    def test_14_ai1_workflow_ideas_are_visible_and_cleared_with_library(self):
        imported = self.client.post(f'/api/days/{self.date}/plan', json={
            'ai': 1,
            'text': self.planner_lines(),
            'allow_similar': True,
        })
        self.assertEqual(imported.status_code, 200, imported.text)

        workflow = self.client.get('/api/overview', params={'date': self.date}).json()
        ai1_items = [item for item in workflow['items'] if item['ai'] == 1]
        library = self.client.get('/api/library').json()
        library_items = {item['id']: item for item in library['items']}
        self.assertEqual(len(ai1_items), 14)
        self.assertEqual(library['workflow_count'], 14)
        self.assertEqual(library['total_count'], len(library['items']))
        self.assertEqual(
            sum(item['in_workflow'] and item['workflow_ai'] == 1 for item in library['items']),
            14,
        )
        for item in ai1_items:
            current_idea = library_items[item['id']]
            self.assertTrue(current_idea['in_workflow'])
            self.assertEqual(current_idea['workflow_ai'], 1)
            self.assertEqual(current_idea['workflow_status'], item['status'])

        cleared = self.client.delete('/api/library')

        self.assertEqual(cleared.status_code, 200, cleared.text)
        self.assertEqual(cleared.json()['workflow_cleared_count'], 14)
        library_after_delete = self.client.get('/api/library').json()
        self.assertEqual(library_after_delete['items'], [])
        self.assertEqual(library_after_delete['workflow_count'], 0)
        self.assertEqual(
            self.client.get('/api/overview', params={'date': self.date}).json()['items'],
            [],
        )

    def test_clear_current_ideas_then_each_import_updates_workflow(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create('2026-11-08').status_code, 201)
        original = self.client.get('/api/overview', params={'date': self.date}).json()
        archived = original['items'][0]
        archive_url = f'/api/days/{self.date}/items/{archived["uid"]}'
        self.assertEqual(
            self.client.post(archive_url + '/copied', json={'mode': 'full'}).status_code,
            200,
        )
        self.assertEqual(self.client.post(archive_url + '/toggle-done').status_code, 200)
        self.assertEqual(self.client.post(archive_url + '/archive').status_code, 200)
        archived_ids_before = {
            item['id'] for item in self.client.get('/api/archive').json()['items']
        }
        self.assertEqual(self.client.get('/api/library').json()['available_count'], 42)

        cleared = self.client.delete('/api/library')

        self.assertEqual(cleared.status_code, 200, cleared.text)
        self.assertEqual(cleared.json()['workflow_cleared_count'], 83)
        self.assertEqual(cleared.json()['days_preserved'], 2)
        self.assertEqual(self.client.get('/api/library').json()['available_count'], 0)
        self.assertEqual(self.client.post('/api/library/reset').status_code, 409)
        emptied = self.client.get('/api/overview', params={'date': self.date}).json()
        self.assertEqual(emptied['items'], [])
        self.assertEqual(emptied['stats']['total'], 0)
        self.assertEqual(
            {item['id'] for item in self.client.get('/api/archive').json()['items']},
            archived_ids_before,
        )

        duplicate_line = (
            f'01 || {archived["title"]} || {archived["hero"]} || {archived["antagonist"]} || '
            f'{archived["conflict"]} || {archived["evidence"]} || {archived["reversal"]} || {archived["ending"]}'
        )
        planned_batch = '\n'.join([duplicate_line, *self.planner_lines().splitlines()[1:]])

        workflow_date = '2026-11-10'
        for ai in (1, 2, 3):
            imported = self.client.post(f'/api/days/{workflow_date}/plan', json={
                'ai': ai,
                'text': planned_batch,
                'allow_similar': True,
            })
            self.assertEqual(imported.status_code, 200, imported.text)
            workflow = self.client.get('/api/overview', params={
                'date': workflow_date,
            }).json()
            self.assertEqual(workflow['stats']['total'], 14 * ai)
            library = self.client.get('/api/library').json()
            self.assertEqual(library['workflow_count'], 14 * ai)
            self.assertEqual(library['available_count'], 0)
            self.assertEqual(library['total_count'], 14 * ai)

        workflow_items = self.client.get('/api/overview', params={
            'date': workflow_date,
        }).json()['items']
        self.assertEqual(len(workflow_items), 42)
        self.assertEqual({item['ai'] for item in workflow_items}, {1, 2, 3})
        self.assertTrue(all(item['id'].startswith('CUSTOM-') for item in workflow_items))

        scan = self.client.get('/api/days/' + workflow_date + '/scan')
        self.assertEqual(scan.status_code, 200, scan.text)
        self.assertTrue(any(
            pair['second'].get('archived')
            and pair['second']['title'] == archived['title']
            for pair in scan.json()['pairs']
        ))

    def test_day_creation_warns_about_similar_archived_stories(self):
        self.create()
        item = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
        base = f'/api/days/{self.date}/items/{item["uid"]}'
        self.client.post(base + '/copied', json={'mode': 'full'})
        self.client.post(base + '/toggle-done')
        self.client.post(base + '/archive')
        duplicate_line = (
            f'01 || {item["title"]} || {item["hero"]} || {item["antagonist"]} || '
            f'{item["conflict"]} || {item["evidence"]} || {item["reversal"]} || {item["ending"]}'
        )
        planned_batch = '\n'.join([duplicate_line, *self.planner_lines().splitlines()[1:]])
        with self.store.edit() as db:
            db['retired_idea_ids'] = sorted({
                *db['retired_idea_ids'],
                *(brief['id'] for brief in core.seed_bank()),
            })
            db['library'] = [
                {key: idea[key] for key in core.KEYS}
                | {'id': idea['id'], 'source': 'imported'}
                for _ in range(3)
                for idea in core.parse_planner(planned_batch, 1)
            ]

        created = self.create('2026-11-08')

        self.assertEqual(created.status_code, 201, created.text)
        self.assertTrue(any(
            warning['archive_title'] == item['title']
            for warning in created.json()['archive_duplicates']
        ))

    def test_expired_archived_ideas_do_not_return_to_current_pool(self):
        self.create()
        item = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
        with self.store.edit() as db:
            archived = next(
                entry for entry in db['days'][self.date]['items']
                if entry['uid'] == item['uid']
            )
            archived['archived_at'] = '2020-01-01T00:00:00'

        response = self.client.get('/api/library')

        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn(item['id'], {idea['id'] for idea in response.json()['items']})
        self.assertIn(item['id'], self.store.read()['retired_idea_ids'])

    def test_reset_idea_library_replaces_only_with_unused_starters(self):
        self.create()
        self.create('2026-11-08')
        items = self.client.get('/api/overview', params={'date': self.date}).json()['items']
        archived = items[0]
        base = f'/api/days/{self.date}/items/{archived["uid"]}'
        self.client.post(base + '/copied', json={'mode': 'full'})
        self.client.post(base + '/toggle-done')
        self.assertEqual(self.client.post(base + '/archive').status_code, 200)

        saved_template = self.client.put(
            '/api/prompt-templates/full', json={'content': 'FULL {{title}}'}
        )
        self.assertEqual(saved_template.status_code, 200)
        reset = self.client.post('/api/library/reset')

        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertEqual(reset.json()['library_size'], 42)
        db = self.store.read()
        library_ids = {brief['id'] for brief in db['library']}
        used_ids = core.archived_ids(db)
        self.assertEqual(len(library_ids), 42)
        self.assertFalse(library_ids & used_ids)
        self.assertEqual(len({brief['theme'] for brief in db['library']}), 14)
        next_day = self.create('2026-11-09')
        self.assertEqual(next_day.status_code, 201, next_day.text)
        next_items = self.client.get('/api/overview', params={
            'date': '2026-11-09',
        }).json()['items']
        self.assertEqual(len(next_items), 42)
        self.assertEqual(len(self.client.get('/api/archive').json()['items']), 1)
        self.assertEqual(
            self.client.get('/api/overview', params={'date': self.date}).json()['stats']['total'],
            41,
        )
        self.assertEqual(db['prompt_templates']['full'], 'FULL {{title}}')

    def test_reset_idea_library_refuses_when_all_126_starters_are_used(self):
        self.create()
        self.create('2026-11-08')
        self.create('2026-11-09')
        before = self.store.read()['library']

        reset = self.client.post('/api/library/reset')

        self.assertEqual(reset.status_code, 409)
        self.assertEqual(self.store.read()['library'], before)
        self.assertEqual(self.client.get('/api/overview', params={'date': self.date})
                         .json()['stats']['total'], 42)

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

    def test_planning_prompt_can_be_customized_and_reset(self):
        url = f'/api/planning-prompt?date={self.date}&ai=1'
        default = self.client.get(url)
        self.assertEqual(default.status_code, 200, default.text)
        self.assertFalse(default.json()['custom'])

        custom_text = 'Write 14 short ideas using my own preferred style.'
        saved = self.client.put('/api/planning-prompt', json={'content': custom_text})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json(), {'text': custom_text, 'custom': True})
        self.assertEqual(self.client.get(url).json(), {'text': custom_text, 'custom': True})

        reset = self.client.delete(url)
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertFalse(reset.json()['custom'])
        self.assertEqual(reset.json()['text'], default.json()['text'])

    def test_new_day_import_after_exhaust(self):
        self.create()
        self.create('2026-11-08')
        self.create('2026-11-09')
        new_date = '2026-11-10'
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

    def test_workspace_status_keeps_replacement_and_ignores_archived_lane_slots(self):
        self.create()
        items = self.client.get('/api/overview', params={'date': self.date}).json()['items']
        removed = items[0]
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            'os.environ', {'THANGMIA_WORKSPACE_DIR': directory}
        ):
            deleted = self.client.delete(f'/api/days/{self.date}/items/{removed["uid"]}')
            self.assertEqual(deleted.status_code, 200, deleted.text)
            status = self.client.get('/api/workspace/status', params={
                'date': self.date, 'ai': removed['ai'],
            })
            self.assertEqual(status.status_code, 200, status.text)
            self.assertEqual(len(status.json()['items']), 14)
            self.assertIn(removed['lane_slot'], [item['slot'] for item in status.json()['items']])
            replacement = next(item for item in self.client.get('/api/overview', params={
                'date': self.date,
            }).json()['items'] if item['slot'] == removed['slot'])
            self.assertNotEqual(replacement['uid'], removed['uid'])

            next_item = next(item for item in items if item['ai'] == removed['ai'] and item['uid'] != removed['uid'])
            base = f'/api/days/{self.date}/items/{next_item["uid"]}'
            self.client.post(base + '/copied', json={'mode': 'full'})
            self.client.post(base + '/toggle-done')
            self.assertEqual(self.client.post(base + '/archive').status_code, 200)
            archived_status = self.client.get('/api/workspace/status', params={
                'date': self.date, 'ai': removed['ai'],
            })
            self.assertEqual(archived_status.status_code, 200, archived_status.text)
            self.assertEqual(len(archived_status.json()['items']), 13)

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

    def test_deleting_ready_item_replaces_it_and_keeps_lane_full(self):
        self.create()
        item = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
        used_ids = core.archived_ids(self.store.read())
        base = f'/api/days/{self.date}/items/{item["uid"]}'
        deleted = self.client.delete(base)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        replacement = deleted.json()['item']
        self.assertNotEqual(replacement['uid'], item['uid'])
        self.assertNotEqual(replacement['id'], item['id'])
        self.assertNotIn(replacement['id'], used_ids)
        self.assertEqual(replacement['theme'], item['theme'])
        self.assertEqual(replacement['ai'], item['ai'])
        self.assertEqual(replacement['slot'], item['slot'])
        overview = self.client.get('/api/overview', params={'date': self.date}).json()
        self.assertEqual(overview['stats']['total'], 42)
        self.assertTrue(any(candidate['uid'] == replacement['uid'] for candidate in overview['items']))
        self.assertEqual(sum(candidate['ai'] == item['ai'] for candidate in overview['items']), 14)
        self.assertNotIn(item['id'], {candidate['id'] for candidate in
                                     self.client.get('/api/library').json()['items']})
        db = self.store.read()
        self.assertIn(item['id'], db['retired_idea_ids'])
        self.assertNotIn(item['id'], {brief['id'] for brief in db['library']})
        remaining = self.client.get('/api/overview', params={'date': self.date}).json()['ideas_remaining']
        self.assertEqual(remaining, 125)
        self.assertEqual(self.client.post('/api/library/reset').status_code, 200)
        self.assertNotIn(item['id'], {brief['id'] for brief in self.store.read()['library']})
        self.assertEqual(self.client.delete(base).status_code, 404)

    def test_delete_is_refused_when_no_unused_same_theme_idea_can_fill_slot(self):
        self.create()
        self.create('2026-11-08')
        self.create('2026-11-09')
        item = self.client.get('/api/overview', params={'date': self.date}).json()['items'][0]
        before = self.client.get('/api/overview', params={'date': self.date}).json()

        response = self.client.delete(f'/api/days/{self.date}/items/{item["uid"]}')

        self.assertEqual(response.status_code, 409)
        self.assertIn('bổ sung ý tưởng mới', response.json()['detail'])
        after = self.client.get('/api/overview', params={'date': self.date}).json()
        self.assertEqual(after['stats']['total'], before['stats']['total'])
        self.assertTrue(any(candidate['uid'] == item['uid'] for candidate in after['items']))

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
