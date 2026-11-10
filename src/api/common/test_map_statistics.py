"""Contracts introduced by the coordinated map/statistics client integration."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import requests
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory

from common.connections import fetch_connections_counts
from common.test_regression_audit import authenticated
from document.models import ShortRef, Source, SourceVoyageConnection
from voyage.models import Voyage
from voyage.serializers import VoyageCrossTabRequestSerializer
from voyage.views import VoyageBibliography, VoyageCrossTabs, VoyageGET, VoyageList


class ConnectionsClientTests(SimpleTestCase):
    @patch('common.connections.requests.post')
    def test_counts_use_typed_ids_and_bounded_timeout(self, post):
        post.return_value.json.return_value = {'voyages': {'123': 7}}
        with patch('common.connections.localsettings.PEOPLE_NETWORKS_BASE_URL', 'http://fixture.invalid/'), \
             patch('common.connections.localsettings.PEOPLE_NETWORKS_TIMEOUT', 2, create=True):
            self.assertEqual(fetch_connections_counts('voyages', [123]), {123: 7})
        post.assert_called_once_with('http://fixture.invalid/counts/', json={'voyages': [123]}, timeout=2)

    @patch('common.connections.requests.post')
    def test_empty_requests_and_unavailable_service_do_not_invent_counts(self, post):
        self.assertEqual(fetch_connections_counts('voyages', []), {})
        post.assert_not_called()
        for failure in [requests.Timeout('fixture timeout'), requests.HTTPError('fixture unavailable'), ValueError('malformed fixture')]:
            with self.subTest(failure=type(failure).__name__):
                post.side_effect = failure
                self.assertIsNone(fetch_connections_counts('voyages', [123]))


class MapStatisticsAPIContracts(TestCase):
    def setUp(self):
        # A public voyage ID must never accidentally resolve to another row's PK.
        self.voyage = Voyage.objects.create(id=990150, voyage_id=990160, dataset=0)
        self.decoy = Voyage.objects.create(id=990160, voyage_id=990170, dataset=1)

    def test_bibliography_uses_public_ids_and_deduplicates_citations(self):
        short_ref = ShortRef.objects.create(name='Issue93 bibliography')
        source = Source.objects.create(short_ref=short_ref, title='Archive', bib='<p><a href="https://fixture.invalid">Archive 2</a>.</p>')
        duplicate = Source.objects.create(short_ref=short_ref, title='Duplicate', bib='Archive 2.')
        excluded = Source.objects.create(short_ref=short_ref, title='Other', bib='Wrong voyage')
        for record, voyage, page in [(source, self.voyage, '10'), (source, self.voyage, '2'),
                                    (duplicate, self.voyage, '2'), (excluded, self.decoy, '1')]:
            SourceVoyageConnection.objects.create(source=record, voyage=voyage, page_range=page)
        response = VoyageBibliography.as_view()(authenticated('/voyage/bibliography/', {
            'voyage_ids': [self.voyage.voyage_id, self.voyage.voyage_id],
        }))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), ['Archive 2 (2; 10).'])

    def test_bibliography_requires_authentication_and_valid_ids(self):
        view = VoyageBibliography.as_view()
        with self.assertNumQueries(0):
            response = view(APIRequestFactory().post('/voyage/bibliography/', {'voyage_ids': []}, format='json'))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(view(authenticated('/voyage/bibliography/', {'voyage_ids': ['bad']})).status_code, 400)
        response = view(authenticated('/voyage/bibliography/', {'voyage_ids': []}))
        self.assertEqual(json.loads(response.content), [])

    @patch('voyage.views.fetch_connections_counts')
    def test_detail_and_list_counts_use_database_ids_without_changing_public_identity(self, fetch):
        fetch.return_value = {self.voyage.pk: 8}
        response = VoyageGET.as_view()(authenticated('/voyage/990160', method='get'), voyage_id=990160)
        self.assertEqual((response.data['id'], response.data['voyage_id'], response.data['connections_count']),
                         (self.voyage.pk, self.voyage.voyage_id, 8))
        fetch.assert_called_once_with('voyages', [self.voyage.pk])
        payload = {'filter': [{'varName': 'voyage_id', 'op': 'exact', 'searchTerm': 990160}], 'page': 1, 'page_size': 10}
        for counts, expected in [({self.voyage.pk: 8}, 8), ({}, 0), (None, None)]:
            fetch.return_value = counts
            response = VoyageList.as_view()(authenticated('/voyage/', payload))
            self.assertEqual(json.loads(response.content)['results'][0]['connections_count'], expected)

    @patch('voyage.views.fetch_connections_counts')
    @patch('voyage.views.redis_cache')
    @patch('voyage.views.use_redis', return_value=('fixture-cache-key', None))
    @patch('voyage.views.USE_REDIS_CACHE', True)
    def test_count_failures_are_not_cached_but_recovery_is(self, use, cache, fetch):
        payload = {'page': 1, 'page_size': 10}
        fetch.return_value = None
        self.assertEqual(VoyageList.as_view()(authenticated('/voyage/', payload)).status_code, 200)
        cache.set.assert_not_called()
        fetch.return_value = {self.voyage.pk: 2, self.decoy.pk: 0}
        self.assertEqual(VoyageList.as_view()(authenticated('/voyage/', payload)).status_code, 200)
        cache.set.assert_called_once()
        self.assertEqual(json.loads(cache.set.call_args.args[1])['results'][0]['connections_count'], 2)

    @patch('voyage.views.requests.post')
    def test_compact_and_csv_responses_preserve_filters_and_selected_ids(self, post):
        payload = {
            'columns': ['voyage_ship__imputed_nationality__name'],
            'rows': 'voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year',
            'rows_label': 'Year', 'value_field': 'voyage_slaves_numbers__imp_total_num_slaves_embarked',
            'agg_fn': 'sum', 'filter': [{'varName': 'dataset', 'op': 'exact', 'searchTerm': 0}],
            'order_by': ['-All'], 'limit': 1, 'offset': 0,
        }
        table = dict(row_label='Year', column_labels=['Nation'], value_label='Embarked', columns=[['All']],
                     rows=['1801'], values=[[2]], totals=[2], metadata=dict(total_results_count=1, offset=0, limit=1))
        for extras, upstream, content_type in [({}, table, 'application/json'),
                ({'csv_output': True}, {'data': 'Year,All\n1801,2\nAll,2\n', 'metadata': table['metadata']}, 'application/json'),
                ({'format': 'csv'}, 'Year,All\n1801,2\nAll,2\n', 'text/csv')]:
            with self.subTest(extras=extras):
                text = upstream if isinstance(upstream, str) else json.dumps(upstream)
                post.return_value = SimpleNamespace(ok=True, text=text, content=text.encode())
                response = VoyageCrossTabs.as_view()(authenticated('/voyage/crosstabs/', {**payload, **extras}))
                self.assertEqual(response.status_code, 200, response.content)
                self.assertTrue(response['Content-Type'].startswith(content_type))
                forwarded = json.loads(post.call_args.kwargs['data'])
                self.assertEqual(forwarded['ids'], [self.voyage.pk])
                self.assertEqual(forwarded['filter'], payload['filter'])
                if extras.get('format') == 'csv':
                    self.assertIn('attachment', response['Content-Disposition'])
                    self.assertEqual(response.content.decode(), upstream)
                else:
                    self.assertEqual(json.loads(response.content), upstream)


class CrosstabInputBoundsTests(SimpleTestCase):
    def test_invalid_bin_and_paging_sizes_are_rejected(self):
        data = dict(columns=['voyage_ship__imputed_nationality__name'],
                    rows='voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year',
                    value_field='voyage_slaves_numbers__imp_total_num_slaves_embarked', agg_fn='sum')
        for field, value in [('binsize', 0), ('binsize', -1), ('offset', -1), ('limit', -1)]:
            with self.subTest(field=field, value=value):
                serializer = VoyageCrossTabRequestSerializer(data={**data, field: value})
                self.assertFalse(serializer.is_valid())
                self.assertIn(field, serializer.errors)
