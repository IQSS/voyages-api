from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .serializers import EnslavedSerializer


class MissingVoyageDateTests(SimpleTestCase):
    @patch('past.serializers.Voyage.objects.filter')
    def test_missing_arrival_year_preserves_both_voyage_identifiers(self, voyages):
        voyages.return_value.first.return_value = SimpleNamespace(
            id=17, voyage_id=4822,
            voyage_itinerary=SimpleNamespace(
                imp_principal_place_of_slave_purchase=None,
                imp_principal_port_slave_dis=None,
            ),
            voyage_dates=SimpleNamespace(imp_arrival_at_port_of_dis_sparsedate=None),
            voyage_ship=SimpleNamespace(ship_name='Concepción'),
            voyage_outcome=SimpleNamespace(particular_outcome=None),
        )
        data = EnslavedSerializer().get_voyages(SimpleNamespace(id=192048))
        self.assertEqual((data['id'], data['voyage_id']), (17, 4822))
        self.assertIsNone(data['year'])
        self.assertIsNone(data['month'])
        self.assertIsNone(data['day'])
