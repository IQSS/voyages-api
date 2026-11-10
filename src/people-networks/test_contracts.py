"""Connection counts must describe the existing graph endpoint, including hops."""
import importlib
import sys
import types
import unittest
from unittest.mock import patch

import networkx as nx

local = types.ModuleType('localsettings')
local.DJANGO_BASE_URL = 'http://fixture.invalid/'
local.DJANGO_AUTH_KEY = 'fixture-only'
sys.modules['localsettings'] = local
utils = importlib.import_module('utils')
with patch.object(utils, 'load_graph', return_value=nx.Graph()), patch('threading.Thread.start'):
    service = importlib.import_module('app')


def fixture():
    graph = nx.Graph()
    for name, cls, pk in [('a', 'enslaved', 1), ('b', 'enslaved', 2),
                          ('c', 'enslavers', 3), ('d', 'enslavers', 4),
                          ('v', 'voyages', 5), ('w', 'voyages', 6),
                          ('r', 'enslavement_relations', 7), ('alone', 'voyages', 8)]:
        graph.add_node(name, uuid=name, id=pk, node_class=cls)
    graph.add_edges_from([('a', 'r'), ('b', 'r'), ('c', 'r'), ('v', 'r'), ('c', 'w'), ('w', 'd')])
    return graph


class ConnectionsContracts(unittest.TestCase):
    def setUp(self):
        service.G = fixture()
        service.HOPS = dict(enslaved=3, enslavers=2, voyages=2, enslavement_relations=2)
        service.CONNECTIONS_INDEX = None
        service.app.config['TESTING'] = True
        self.client = service.app.test_client()

    def test_index_matches_actual_network_for_every_node_and_hop_depth(self):
        for levels in [0, 1, 2, 3]:
            service.HOPS = {cls: levels for cls in service.HOPS}
            service.CONNECTIONS_INDEX = utils.build_connections_index(service.G, service.HOPS)
            for name, data in service.G.nodes(data=True):
                with self.subTest(node=name, levels=levels):
                    request = {data['node_class']: [data['id']]}
                    network = self.client.post('/', json=request)
                    counts = self.client.post('/counts/', json=request)
                    self.assertEqual(network.status_code, 200)
                    self.assertEqual(counts.status_code, 200)
                    self.assertEqual(counts.json[data['node_class']][str(data['id'])],
                                     len(network.json['nodes']) - 1)
                    self.assertEqual(len(network.json['nodes']), len({row['uuid'] for row in network.json['nodes']}))

    def test_unavailable_index_is_503_then_recovers_without_affecting_network(self):
        self.assertEqual(self.client.post('/counts/', json={'voyages': [5]}).status_code, 503)
        self.assertEqual(self.client.post('/', json={'voyages': [5]}).status_code, 200)
        with patch.object(service, 'build_connections_index', side_effect=RuntimeError('fixture failure')):
            service._build_connections_index_in_background()
        self.assertEqual(self.client.post('/counts/', json={'voyages': [5]}).status_code, 503)
        service._build_connections_index_in_background()
        self.assertEqual(self.client.post('/counts/', json={'voyages': [5]}).status_code, 200)

    def test_unknown_and_isolated_ids_have_no_invented_connections(self):
        service._build_connections_index_in_background()
        result = self.client.post('/counts/', json={'voyages': [8, 99999]}).json
        self.assertEqual(result, {'voyages': {'8': 0}})
        self.assertEqual(self.client.post('/counts/', json={}).json, {})


if __name__ == '__main__':
    unittest.main()
