from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from .serializers import EnslavedSerializer, EnslavedListRequestSerializer, EnslaverListRequestSerializer
from .models import Enslaved, Gender, EnslaverIdentity
from common.reqs import post_req
from common.static.Enslaved_options import Enslaved_options
from common.static.EnslaverIdentity_options import EnslaverIdentity_options


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


class PublicMenuFilterTests(TestCase):
    def test_related_gender_menu_filter_validates_and_selects_matching_people(self):
        female = Gender.objects.create(name='Female')
        male = Gender.objects.create(name='Male')
        match = Enslaved.objects.create(enslaved_id=870001, gender=female)
        Enslaved.objects.create(enslaved_id=870002, gender=male)
        Enslaved.objects.create(enslaved_id=870003, gender=None)
        request = EnslavedListRequestSerializer(data={
            'filter': [{'varName': 'gender__name', 'op': 'in', 'searchTerm': ['Female']}],
        })
        self.assertTrue(request.is_valid(), request.errors)
        matches, count, _, _, errors = post_req(
            Enslaved.objects.all(), None, dict(request.validated_data),
            Enslaved_options, auto_prefetch=False,
        )
        self.assertEqual(errors, [])
        self.assertEqual(count, 1)
        self.assertEqual(list(matches.values_list('pk', flat=True)), [match.pk])
        self.assertIn('gender', Enslaved_options)

    @patch('common.reqs.global_search')
    def test_supported_source_search_menu_filter_validates_for_identities(self, source_search):
        match = EnslaverIdentity.objects.create(principal_alias='Fixture match')
        EnslaverIdentity.objects.create(principal_alias='Fixture other')
        source_search.return_value = (EnslaverIdentity.objects.filter(pk=match.pk), 1)
        request = EnslaverListRequestSerializer(data={
            'filter': [{'varName': 'enslaver__source__ALL', 'op': 'icontains', 'searchTerm': 'fixture source'}],
        })
        self.assertTrue(request.is_valid(), request.errors)
        self.assertEqual(request.validated_data['filter'][0]['varName'], 'enslaver__source__ALL')
        self.assertEqual(EnslaverIdentity_options['enslaver__source__ALL'], {'type': 'string', 'many': True})
        matches, count, _, _, errors = post_req(
            EnslaverIdentity.objects.all(), None, dict(request.validated_data),
            EnslaverIdentity_options, auto_prefetch=False,
        )
        self.assertEqual(errors, [])
        self.assertEqual(count, 1)
        self.assertEqual(list(matches.values_list('pk', flat=True)), [match.pk])
        self.assertEqual(source_search.call_args.args[1], 'fixture source')
        self.assertEqual(source_search.call_args.kwargs, {'core_name': 'enslaversources'})

    def test_unknown_related_fields_are_still_rejected(self):
        request = EnslavedListRequestSerializer(data={
            'filter': [{'varName': 'gender__unknown', 'op': 'in', 'searchTerm': ['Female']}],
        })
        self.assertFalse(request.is_valid())
