import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError, OperationalError, close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from rest_framework.authtoken.models import Token

from .models import Publication
from .publication import payload_hash, process_publication
from .tests import FIXTURE, _model_for_table
from .views import ChangeSetProcessor
from voyage.models import Voyage
from document.models import Source


class ContributionContractTests(TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text())
        for row in self.fixture['seed']:
            _model_for_table(row['table']).objects.create(pk=row['pk'], **row['fields'])
        self.payload = {
            'key': 'test-publication',
            'changeset': self.fixture['steps'][0]['changeset'],
            'contribution_ids': ['test-contribution'],
        }
        self.header = {'HTTP_AUTHORIZATION': 'Bearer contribution-service-tests-only'}

    def submit(self, payload=None, **headers):
        return self.client.post('/contrib/publish_batch', payload or self.payload,
                                content_type='application/json', **(headers or self.header))

    def test_service_endpoints_reject_browser_and_missing_credentials(self):
        for path, method in [('/contrib/data', 'post'), ('/contrib/publish_batch', 'post'),
                             ('/contrib/publication_status/test-publication', 'get')]:
            for token in ['', 'Token public-browser-token', 'Bearer wrong-token']:
                response = getattr(self.client, method)(path, HTTP_AUTHORIZATION=token)
                self.assertEqual(response.status_code, 401)
        self.assertEqual(Publication.objects.count(), 0)

    @override_settings(CONTRIB_SERVICE_TOKEN='')
    def test_missing_service_configuration_fails_closed(self):
        self.assertEqual(self.submit().status_code, 503)

    def test_location_tree_uses_existing_django_auth(self):
        self.assertEqual(self.client.get('/contrib/location_tree').status_code, 401)
        token = Token.objects.create(user=get_user_model().objects.create(username='browser'))
        response = self.client.get('/contrib/location_tree', HTTP_AUTHORIZATION='Token ' + token.key)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_queries_cannot_read_auth_models_or_traverse_relations(self):
        cases = [
            ('auth_user', ['password'], []),
            ('voyage_voyage', ['voyage_ship__name'], []),
            ('voyage_voyage', [], []),
            ('voyage_voyage', ['id'], [{'field': 'voyage_id__gt', 'value': 0}]),
            ('voyage_voyage', ['id'], [{'field': 'voyage_id', 'value': 0, 'operator': 'gte'}]),
        ]
        for model, fields, filters in cases:
            response = self.client.post('/contrib/data', {'q': {'query': {'model': model, 'filter': filters}, 'fields': fields}}, content_type='application/json', **self.header)
            self.assertEqual(response.status_code, 400, response.content)

    def test_queries_keep_foreign_key_column_names(self):
        voyage = Voyage.objects.create(voyage_id=100, dataset=0, voyage_groupings_id=1)
        response = self.client.post('/contrib/data', {'q': {'query': {'model': 'voyage_voyage', 'filter': [{'field': 'id', 'value': [voyage.pk], 'operator': 'in'}]}, 'fields': ['id', 'voyage_groupings_id']}}, content_type='application/json', **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'q': [{'id': voyage.pk, 'voyage_groupings_id': 1}]})

    def test_publication_survives_retries_and_keeps_public_id_distinct(self):
        self.assertEqual(self.submit().status_code, 202)
        process_publication(self.payload['key'])
        record = Publication.objects.get()
        self.assertEqual(record.status, 'completed')
        voyage = Voyage.objects.get(voyage_id=900001)
        self.assertNotEqual(voyage.pk, voyage.voyage_id)
        first_result = record.result
        with patch.object(ChangeSetProcessor, 'process_changeset', side_effect=AssertionError('replayed')):
            process_publication(self.payload['key'])
            response = self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id_mappings'], first_result['id_mappings'])
        self.assertEqual(Voyage.objects.filter(voyage_id=900001).count(), 1)

    def test_idempotency_key_is_bound_to_exact_payload(self):
        self.submit()
        changed = copy.deepcopy(self.payload)
        changed['contribution_ids'].append('another-contribution')
        self.assertEqual(self.submit(changed).status_code, 409)
        changed = copy.deepcopy(self.payload)
        changed['changeset']['updates'][0]['changes'][0]['changed'] = 900002
        self.assertEqual(self.submit(changed).status_code, 409)
        self.assertEqual(Publication.objects.count(), 1)

    def test_pending_job_is_rescheduled_after_process_loss(self):
        self.submit()
        with patch('contrib.publication.schedule_publication') as schedule, self.captureOnCommitCallbacks(execute=True):
            response = self.client.get('/contrib/publication_status/' + self.payload['key'], **self.header)
        self.assertEqual(response.json()['status'], 'pending')
        schedule.assert_called_once_with(self.payload['key'])

    def test_failed_changes_roll_back_before_recording_failure(self):
        self.submit()
        def fail(_processor, task):
            Voyage.objects.create(voyage_id=999999, dataset=0)
            raise ValueError('invalid fixture change')
        with patch.object(ChangeSetProcessor, 'process_changeset', fail):
            process_publication(self.payload['key'])
        self.assertFalse(Voyage.objects.filter(voyage_id=999999).exists())
        self.assertEqual(Publication.objects.get().status, 'failed')
        self.assertEqual(self.submit().status_code, 400)

    def test_database_interruption_keeps_retryable_pending_record(self):
        self.submit()
        def fail(_processor, task):
            Voyage.objects.create(voyage_id=999999, dataset=0)
            raise OperationalError('connection interrupted')
        with patch.object(ChangeSetProcessor, 'process_changeset', fail), self.assertRaises(OperationalError):
            process_publication(self.payload['key'])
        self.assertFalse(Voyage.objects.filter(voyage_id=999999).exists())
        self.assertEqual(Publication.objects.get().status, 'pending')
        process_publication(self.payload['key'])
        self.assertEqual(Publication.objects.get().status, 'completed')

    def test_result_commit_failure_rolls_back_published_data(self):
        self.submit()
        with patch.object(Publication, 'save', side_effect=OperationalError('commit interrupted')), self.assertRaises(OperationalError):
            process_publication(self.payload['key'])
        self.assertFalse(Voyage.objects.filter(voyage_id=900001).exists())
        self.assertEqual(Publication.objects.get().status, 'pending')
        process_publication(self.payload['key'])
        self.assertEqual(Voyage.objects.filter(voyage_id=900001).count(), 1)

    def test_publication_rejects_unknown_columns_and_primary_key_updates(self):
        for field in ('password', 'id', 'voyage_ship__name'):
            payload = copy.deepcopy(self.payload)
            payload['changeset']['updates'][0]['changes'][0]['property'] = field
            self.assertEqual(self.submit(payload).status_code, 400)
        self.assertFalse(Publication.objects.exists())

    def source_date_payload(self, schema):
        payload = copy.deepcopy(self.payload)
        updates = payload['changeset']['updates']
        updates.append({'entityRef': {'type': 'new', 'schema': schema, 'id': 'source-date'},
                        'changes': [{'property': 'year', 'changed': 1901}]})
        source = next(update for update in updates if update['entityRef']['schema'] == 'Voyage Source')
        source['changes'].append({'property': 'date_id', 'changed': 'source-date', 'isForeignKey': True})
        return payload

    def test_source_date_uses_document_date_table(self):
        self.assertEqual(self.submit(self.source_date_payload('SourceDate')).status_code, 202)
        process_publication(self.payload['key'])
        self.assertEqual(Publication.objects.get().status, 'completed')
        self.assertEqual(Source.objects.get(title='Fixture source').date.year, 1901)

    def test_source_date_cannot_reference_a_voyage_date(self):
        self.assertEqual(self.submit(self.source_date_payload('VoyageSparseDate')).status_code, 202)
        process_publication(self.payload['key'])
        record = Publication.objects.get()
        self.assertEqual(record.status, 'failed')
        self.assertIn('wrong model', record.error)
        self.assertFalse(Source.objects.filter(title='Fixture source').exists())
        self.assertFalse(Voyage.objects.filter(voyage_id=900001).exists())

    def test_payload_hash_is_independent_of_object_key_order(self):
        self.assertEqual(payload_hash({'a': 1, 'b': 2}, []), payload_hash({'b': 2, 'a': 1}, []))


class PublicationConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update_nowait')
    def test_concurrent_workers_cannot_apply_the_same_changes(self):
        changeset = {'updates': [], 'deletions': []}
        Publication.objects.create(key='concurrent', payload_hash=payload_hash(changeset, []), changeset=changeset)
        entered = threading.Event()
        release = threading.Event()

        def publish(_processor, task):
            entered.set()
            if not release.wait(10):
                raise AssertionError('Concurrent worker test timed out')
            Voyage.objects.create(voyage_id=999999, dataset=0)
            return {}

        def worker():
            close_old_connections()
            try:
                process_publication('concurrent')
            finally:
                close_old_connections()

        with patch.object(ChangeSetProcessor, 'process_changeset', publish), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker)
            try:
                self.assertTrue(entered.wait(10))
                with self.assertRaises(DatabaseError):
                    process_publication('concurrent')
            finally:
                release.set()
            future.result(timeout=10)
        process_publication('concurrent')
        self.assertEqual(Voyage.objects.filter(voyage_id=999999).count(), 1)
        self.assertEqual(Publication.objects.get().status, 'completed')
