"""Route lookup mappings describe exactly the selected, rendered network."""
import importlib
import sys
import tempfile
import types
import unittest

import pandas as pd

workspace = tempfile.TemporaryDirectory()
local = types.ModuleType('localsettings')
local.TMP_PATH = workspace.name
local.DJANGO_BASE_URL = 'http://fixture.invalid/'
local.DJANGO_AUTH_KEY = 'fixture-only'
sys.modules['localsettings'] = local
service = importlib.import_module('app')


class RouteMappingContracts(unittest.TestCase):
    def setUp(self):
        service.app.config['TESTING'] = True
        self.client = service.app.test_client()
        self.index = {
            'nodes': pd.DataFrame([
                [901, 'A', 5, 0, 0, 0], [901, 'A', 2, 0, 0, 0],
                [901, 'B', 0, 0, 7, 0], [902, 'A', 3, 0, 0, 0],
                [902, 'C', 0, 0, 3, 0], [903, 'ignored', 9, 0, 0, 0],
            ], columns=['pk', 'id', 'origin', 'embarkation', 'disembarkation', 'post-disembarkation']),
            'edges': pd.DataFrame([
                [901, 'A', 'B', 7, 1, 2, 3, 4],
                [902, 'A', 'C', 3, 5, 6, 7, 8],
                [901, 'A', 'C', 0, 9, 9, 9, 9],
            ], columns=['pk', 'source', 'target', 'weight', 'c1x', 'c2x', 'c1y', 'c2y']),
            'nodesdata': {key: {'name': key} for key in ['A', 'B', 'C']},
            'edgesdata': {'A__B': {'type': 'oceanic'}, 'A__C': {'type': 'oceanic'}},
        }
        service.registered_caches['fixture'] = {'graphs': {'fixture': {'index': self.index}}}

    def response(self, ids):
        response = self.client.post('/network_maps/', json={'pks': ids, 'cachename': 'fixture', 'graphname': 'fixture'})
        self.assertEqual(response.status_code, 200)
        return response.json

    def test_selected_voyage_mapping_is_unique_and_excludes_zero_weight_edges(self):
        result = self.response([901])
        self.assertEqual(result['voyage_mappings'], {'901': {'nodes': ['A', 'B'], 'edges': [['A', 'B']]}})
        self.assertEqual({node['id'] for node in result['nodes']}, {'A', 'B'})
        self.assertEqual(result['edges'], [{'source': 'A', 'target': 'B', 'weight': 7,
                                          'controls': [[1, 3], [2, 4]], 'type': 'oceanic'}])
        self.assertEqual(result['nodes'][0]['weights']['origin'], 7)

    def test_multiple_mappings_match_aggregate_nodes_and_edges(self):
        result = self.response([901, 902, 903])
        self.assertEqual(result['voyage_mappings'], {
            '901': {'nodes': ['A', 'B'], 'edges': [['A', 'B']]},
            '902': {'nodes': ['A', 'C'], 'edges': [['A', 'C']]},
        })
        self.assertEqual(result['nodes'][0]['weights']['origin'], 10)
        before = self.index['edges'].copy(deep=True)
        self.response([902])
        pd.testing.assert_frame_equal(self.index['edges'], before)

    def test_empty_selection_has_no_stale_mapping(self):
        self.assertEqual(self.response([]), {'nodes': [], 'edges': [], 'voyage_mappings': {}})
        for graph in service.voyage_maps['graph_params']:
            self.assertEqual(service.voyage_maps['indices'][graph['name']]['pk'], 'voyage_id')


if __name__ == '__main__':
    unittest.main()
