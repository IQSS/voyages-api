"""Exercise the actual Flask routes with in-memory, independently valued data."""
import csv
import importlib
import io
import json
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

local = types.ModuleType('localsettings')
local.DJANGO_BASE_URL = 'http://fixture.invalid/'
local.DJANGO_AUTH_KEY = 'fixture-only'
sys.modules['localsettings'] = local


def empty_columns(*args, **kwargs):
    fields = json.loads(kwargs['data'])['selected_fields']
    return types.SimpleNamespace(text=json.dumps({field: [] for field in fields}))


with patch('requests.post', side_effect=empty_columns), patch('time.sleep'):
    service = importlib.import_module('app')


class CrosstabContracts(unittest.TestCase):
    def setUp(self):
        self.client = service.app.test_client()
        service.app.config['TESTING'] = True
        service.big_df['options'] = {
            'id': {'type': 'int', 'label': 'ID'},
            'row': {'type': 'str', 'label': 'Origin'},
            'year': {'type': 'int', 'label': 'Year'},
            'col': {'type': 'str', 'label': 'Destination'},
            'region': {'type': 'str', 'label': 'Region'},
            'amount': {'type': 'int', 'label': 'Embarked'},
            'ratio': {'type': 'pct', 'label': 'Proportion'},
        }
        service.big_df['df'] = pd.DataFrame([
            dict(id=1, row='A', year=1801, col='X', region='North', amount=1, ratio=.25),
            dict(id=2, row='A', year=1802, col='Y', region='South', amount=2, ratio=.75),
            dict(id=3, row='B', year=1803, col='X', region='North', amount=5, ratio=.5),
            dict(id=4, row=None, year=None, col=None, region=None, amount=3, ratio=.125),
        ])
        self.payload = dict(ids=[1, 2, 3, 4], columns=['col'], rows='row',
                            rows_label='Origin', value_field='amount', agg_fn='sum')

    def response(self, **changes):
        response = self.client.post('/crosstabs/', json={**self.payload, **changes})
        self.assertEqual(response.status_code, 200)
        return response

    def table(self, **changes):
        return json.loads(self.response(**changes).data)

    def test_compact_table_counts_undefined_without_losing_totals(self):
        table = self.table()
        self.assertEqual(table['columns'], [['X'], ['Y'], ['Undefined'], ['All']])
        self.assertEqual(table['rows'], ['A', 'B', 'Undefined'])
        self.assertEqual(table['values'], [[1, 2, 0, 3], [5, 0, 0, 5], [0, 0, 3, 3]])
        self.assertEqual(table['totals'], [6, 2, 3, 11])
        self.assertEqual(table['metadata'], dict(total_results_count=3, offset=0, limit=None))
        self.assertNotIn('tablestructure', table)
        self.assertNotIn('data', table)

    def test_limit_is_row_count_and_sorting_never_pages_the_totals(self):
        table = self.table(order_by=['-All'], offset=1, limit=1)
        self.assertEqual(table['rows'], ['A'])
        self.assertEqual(table['values'], [[1, 2, 0, 3]])
        self.assertEqual(table['totals'], [6, 2, 3, 11])
        self.assertEqual(table['metadata'], dict(total_results_count=3, offset=1, limit=1))
        self.assertEqual(self.table(limit=0)['rows'], [])
        self.assertEqual(self.table(offset=99)['rows'], [])

    def test_column_paths_and_csv_preserve_requested_sort(self):
        changes = dict(columns=['region', 'col'], order_by=['-North__X'], limit=2)
        table = self.table(**changes)
        response = self.response(format='csv', **changes)
        self.assertTrue(response.content_type.startswith('text/csv'))
        legacy = self.table(csv_output=True, **changes)
        self.assertEqual(legacy['data'], response.data.decode())
        parsed = list(csv.reader(io.StringIO(legacy['data'])))
        self.assertEqual(table['columns'], [['North', 'X'], ['South', 'Y'], ['Undefined', 'Undefined'], ['All']])
        self.assertEqual(table['rows'], ['B', 'A'])
        self.assertEqual([row[0] for row in parsed[-3:]], ['B', 'A', 'All'])
        self.assertEqual([[float(value) for value in row[1:]] for row in parsed[-3:]],
                         table['values'] + [table['totals']])
        self.assertEqual(legacy['metadata'], table['metadata'])

    def test_binned_means_do_not_fill_missing_values_with_zero(self):
        service.big_df['df'].loc[1, 'amount'] = None
        table = self.table(ids=[1, 2, 3], rows='year', rows_label='Year', binsize=10, agg_fn='mean')
        self.assertEqual(table['rows'], ['1801-1803'])
        self.assertEqual(table['values'][0][-1], 3.0)
        self.assertEqual(table['totals'][-1], 3.0)
        self.assertIsInstance(table['values'][0][-1], float)

    def test_year_bins_keep_every_observed_year_and_clip_only_the_last_label(self):
        cases = [
            (10, [1514, 1521], ['1511-1520', '1521-1521'], [1, 2]),
            (10, [1514, 1514], ['1511-1514'], [3]),
            (10, [1520, 1520], ['1511-1520'], [3]),
            (10, [1514, 1537], ['1511-1520', '1531-1537'], [1, 2]),
            (25, [1514, 1537], ['1501-1525', '1526-1537'], [1, 2]),
            (25, [1500, 1525], ['1476-1500', '1501-1525'], [1, 2]),
            (1, [1510, 1511], ['1510', '1511'], [1, 2]),
        ]
        for width, years, labels, counts in cases:
            with self.subTest(width=width, years=years):
                service.big_df['df'] = pd.DataFrame({
                    'id': [1, 2], 'year': years, 'col': ['X', 'X'], 'amount': [1, 2],
                })
                table = self.table(ids=[1, 2], rows='year', rows_label='Year', binsize=width)
                self.assertEqual(table['rows'], labels)
                self.assertEqual([row[-1] for row in table['values']], counts)
                self.assertEqual(table['totals'], [3, 3])

    def test_chart_and_estimate_bins_start_at_the_observed_minimum_and_keep_the_maximum(self):
        for final, group_labels, estimate_labels, counts in [
            (1524, ['1514-1523', '1524-1524'], ['1514-1523', '1524'], [5, 7]),
            (1525, ['1514-1523', '1524-1525'], ['1514-1523', '1524-1525'], [5, 7]),
            (1514, ['1514-1514'], ['1514'], [12]),
        ]:
            with self.subTest(final=final):
                frame = pd.DataFrame({'id': [1, 2], 'year': [1514, final],
                                      'nation__name': ['Spain', 'Portugal'], 'amount': [5, 7]})
                service.big_df['df'] = frame
                service.estimate_pivot_tables['df'] = frame
                group = self.client.post('/groupby/', json={
                    'ids': [1, 2], 'by': 'year__bins__10', 'vals': 'amount', 'agg_fn': 'sum',
                })
                self.assertEqual(group.status_code, 200)
                self.assertEqual(json.loads(group.data), {'year': group_labels, 'amount': counts})
                estimates = self.client.post('/estimates_pivot/', json={
                    'ids': [1, 2], 'rows': ['year'], 'cols': ['nation__name'],
                    'vals': ['amount'], 'binsize': 10, 'mode': 'csv',
                })
                self.assertEqual(estimates.status_code, 200)
                rows = list(csv.DictReader(io.StringIO(json.loads(estimates.data)['data'])))
                self.assertEqual([row[''] for row in rows], [*estimate_labels, 'Totals'])
                self.assertEqual([float(row['Totals']) for row in rows], [*counts, 12])

    def test_percentages_and_normalized_values_remain_fractional(self):
        self.assertEqual(self.table(ids=[1, 2], value_field='ratio', agg_fn='mean')['totals'][-1], .5)
        table = self.table(ids=[1, 2, 3], normalize=['index'])
        self.assertEqual(table['values'][0], [.3333, .6667])
        self.assertEqual(table['values'][1], [1.0, 0.0])
        self.assertEqual(table['totals'], [.75, .25])

    def test_numeric_rows_sort_with_undefined_last(self):
        table = self.table(rows='year', rows_label='Year', order_by=['Year'])
        self.assertEqual(table['rows'], ['1801', '1802', '1803', 'Undefined'])
        table = self.table(rows='year', rows_label='Year', order_by=['-Year'])
        self.assertEqual(table['rows'], ['1803', '1802', '1801', 'Undefined'])

    def test_row_label_csv_sort_matches_canonical_response_order(self):
        # The paired client retains these ranks instead of using locale/natural
        # collation, which would put Alpha 2 before Alpha 10 only in the UI.
        service.big_df['df']['row'] = ['Zulu', 'Alpha 2', 'Alpha 10', None]
        ascending = ['Alpha 10', 'Alpha 2', 'Zulu', 'Undefined']
        self.assertEqual(self.table()['rows'], ascending)
        for key, expected in [('Origin', ascending),
                              ('-Origin', ['Zulu', 'Alpha 2', 'Alpha 10', 'Undefined'])]:
            with self.subTest(key=key):
                table = self.table(order_by=[key])
                self.assertEqual(table['rows'], expected)
                exported = list(csv.reader(io.StringIO(self.response(format='csv', order_by=[key]).data.decode())))
                self.assertEqual([row[0] for row in exported[-len(expected)-1:-1]], expected)
                self.assertEqual(exported[-1][0], 'All')

    def test_legacy_nan_category_is_undefined(self):
        service.big_df['df'].loc[3, 'col'] = 'nan'
        table = self.table()
        self.assertIn(['Undefined'], table['columns'])
        self.assertNotIn(['nan'], table['columns'])
        self.assertEqual(table['totals'][-1], 11)

    def test_empty_result_has_aligned_empty_arrays(self):
        table = self.table(ids=[])
        self.assertEqual([table[key] for key in ['columns', 'rows', 'values', 'totals']], [[], [], [], []])
        self.assertEqual(table['metadata']['total_results_count'], 0)
        self.assertEqual(self.table(ids=[], csv_output=True)['data'], '')


class CacheBuildContracts(unittest.TestCase):
    def test_vectorized_build_keeps_order_spelling_dates_and_many_values(self):
        variables = {
            'id': {'type': 'int'}, 'place': {'type': 'str'}, 'amount': {'type': 'int'},
            'date': {'type': 'obj', 'fields': ['year', 'month', 'day'], 'join': ','},
            'sources': {'type': 'obj', 'many': True, 'fields': ['source']},
            'people': {'type': 'obj', 'many': True, 'fields': ['role', 'person']},
        }
        replies = [
            dict(id=[3, 1, 2], place=['St. Helena', None, 'S. Tomé'], amount=['2', None, '4'],
                 year=[1801, None, 1803], month=[None, None, 2], day=[3, None, None]),
            dict(id=[1, 3, 3], source=['Book A', 'Book B', 'Book C']),
            dict(id=[3, 2], role=['Captain', None], person=['Name', 'Other']),
        ]
        with patch.object(service, 'fetch_columns', side_effect=replies) as fetch:
            result = service.load_long_df('voyage/dataframes/', variables)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(list(result.columns), list(variables))
        self.assertEqual(list(result['id']), [3, 1, 2])
        self.assertEqual(list(result['place']), ['St. Helena', None, 'S. Tomé'])
        self.assertEqual(list(result['date']), ['1801,,3', ',,', '1803,2,'])
        self.assertEqual(list(result['sources']), ['Book B|Book C', 'Book A', 'nan'])
        self.assertEqual(list(result['people']), ['Captain: Name', 'nan', ': Other'])
        self.assertTrue(pd.isna(result.iloc[1]['amount']))


if __name__ == '__main__':
    unittest.main()
