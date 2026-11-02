"""Independent audit probes: real DRF views and MariaDB query behavior."""

from types import SimpleNamespace
from unittest.mock import patch

from blog.models import Post
from blog.views import PostList
from django.test import SimpleTestCase, TestCase, override_settings
from geo.views import GeoTree
from past.models import EnslaverAlias, EnslaverIdentity
from rest_framework.test import APIRequestFactory, force_authenticate
from voyage.models import VoyageDates, VoyageSparseDate
from voyage.serializers import VoyageCrossTabRequestSerializer, VoyageDatesSerializer

from common.models import SavedQuery
from common.reqs import post_req, sort_queryset
from common.static.EnslaverIdentity_options import EnslaverIdentity_options
from common.views import MakeSavedSearch, UseSavedSearch


def authenticated(path, data=None, method="post"):
    request = getattr(APIRequestFactory(), method)(path, data or {}, format="json")
    user = SimpleNamespace(is_authenticated=True, username="audit")
    force_authenticate(request, user=user, token=SimpleNamespace(user=user))
    return request


class GeoAuthenticationAudit(SimpleTestCase):
    @patch("geo.views.GeoTreeFilter", return_value=[])
    def test_anonymous_request_is_rejected_before_query(self, tree):
        response = GeoTree.as_view()(
            APIRequestFactory().post("/geo/geotree/", {}, format="json")
        )
        self.assertEqual(response.status_code, 401)
        tree.assert_not_called()


class ExistingPublicBehaviorAudit(TestCase):
    def test_tied_voyage_years_have_a_unique_order_across_pages(self):
        """Equal years must not move voyages between independently fetched pages."""
        from common.static.Voyage_options import Voyage_options
        from voyage.models import Voyage
        from voyage.views import VoyageList

        year_field = "voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year"
        fixtures = []
        # Separate public IDs, internal PKs, and related-date insertion order.
        for index, year in enumerate([1803] * 13 + [1804] * 3 + [None] * 2):
            voyage = Voyage.objects.create(
                id=990200 + index, voyage_id=991000 - index, dataset=index % 2,
            )
            fixtures.append((voyage, year))
        for voyage, year in reversed(fixtures):
            date = VoyageSparseDate.objects.create(year=year)
            VoyageDates.objects.create(
                voyage=voyage, imp_arrival_at_port_of_dis_sparsedate=date,
            )

        for prefix in ["", "-"]:
            with self.subTest(order_by=prefix + year_field):
                rows = sort_queryset(
                    Voyage.objects.all(), {"order_by": [prefix + year_field]},
                    Voyage_options,
                )
                expected = [
                    voyage.voyage_id
                    for voyage, year in sorted(
                        fixtures,
                        key=lambda item: (
                            item[1] is None,
                            (item[1] or 0) * (1 if prefix else -1),
                            item[0].pk,
                        ),
                    )
                ]
                for page_size in [4, 12]:
                    actual = []
                    for page in range(1, (len(fixtures) - 1) // page_size + 2):
                        response = VoyageList.as_view()(authenticated(
                            "/voyage/", {
                                "order_by": [prefix + year_field],
                                "page": page, "page_size": page_size,
                            },
                        ))
                        self.assertEqual(response.status_code, 200)
                        import json

                        payload = json.loads(response.content)
                        self.assertEqual(payload["count"], len(fixtures))
                        actual.extend(row["voyage_id"] for row in payload["results"])
                    self.assertEqual(actual, expected)
                    self.assertEqual(len(set(actual)), len(fixtures))

                # A coincidental backend tie order is insufficient: the SQL
                # itself must uniquely order tied rows before page slicing.
                compiled_order = rows.query.get_compiler(rows.db).get_order_by()
                final_column = compiled_order[-1][0].expression
                self.assertEqual(final_column.target, Voyage._meta.pk)
                self.assertEqual(final_column.alias, rows.query.base_table)

    def test_default_and_explicit_unique_order_preserve_direction(self):
        from common.static.Voyage_options import Voyage_options
        from voyage.models import Voyage

        voyages = [
            Voyage.objects.create(voyage_id=990300 + i, dataset=0) for i in range(3)
        ]
        ids = [row.pk for row in voyages]
        for parameters, expected in [
            ({}, ids),
            ({"order_by": []}, ids),
            ({"order_by": ["-id"]}, ids),
            ({"order_by": ["id"]}, list(reversed(ids))),
        ]:
            with self.subTest(parameters=parameters):
                rows = sort_queryset(Voyage.objects.all(), parameters, Voyage_options)
                self.assertEqual(list(rows.values_list("pk", flat=True)), expected)

    def test_voyage_cargo_response_uses_connection_amount_and_unit(self):
        from voyage.models import CargoType, CargoUnit, Voyage, VoyageCargoConnection
        from voyage.views import VoyageGET

        voyage = Voyage.objects.create(voyage_id=990101, dataset=0)
        cargo = CargoType.objects.create(name="Sugar")
        unit = CargoUnit.objects.create(name="Barrels")
        connection = VoyageCargoConnection.objects.create(
            voyage=voyage, cargo=cargo, unit=unit, amount=2.0,
        )
        for amount, measurement, expected in [
            (2.0, unit, f"2.0 {unit} Sugar"),
            (None, unit, f"{unit} Sugar"),
            (2.0, None, "2.0 Sugar"),
            (None, None, "Sugar"),
        ]:
            with self.subTest(amount=amount, unit=measurement):
                connection.amount, connection.unit = amount, measurement
                connection.save()
                response = VoyageGET.as_view()(
                    authenticated("/voyage/990101", method="get"), voyage_id=990101,
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["cargo"], [expected])

    def test_related_filter_steps_do_not_reapply_previous_alias_predicates(self):
        match = EnslaverIdentity.objects.create(principal_alias="Both")
        other = EnslaverIdentity.objects.create(principal_alias="Only first")
        EnslaverAlias.objects.bulk_create(
            [
                EnslaverAlias(identity=match, alias="First", manual_id="first"),
                EnslaverAlias(identity=match, alias="Second", manual_id="second"),
                EnslaverAlias(identity=other, alias="First", manual_id="first"),
            ]
        )
        request = {
            "filter": [
                {"varName": "aliases__alias", "op": "exact", "searchTerm": "First"},
                {
                    "varName": "aliases__manual_id",
                    "op": "exact",
                    "searchTerm": "second",
                },
            ]
        }
        rows, count, _, _, errors = post_req(
            EnslaverIdentity.objects.all(),
            None,
            request,
            EnslaverIdentity_options,
            auto_prefetch=False,
        )
        self.assertEqual(errors, [])
        self.assertEqual(count, 1)
        self.assertEqual(list(rows.values_list("pk", flat=True)), [match.pk])

    def test_enslaver_ordering_preserves_nulls_last_and_pagination(self):
        EnslaverIdentity.objects.bulk_create(
            [
                EnslaverIdentity(principal_alias="Unknown", birth_year=None),
                EnslaverIdentity(principal_alias="Later", birth_year=1900),
                EnslaverIdentity(principal_alias="Earlier", birth_year=1800),
            ]
        )
        rows = sort_queryset(
            EnslaverIdentity.objects.all(),
            {"order_by": ["-birth_year"]},
            EnslaverIdentity_options,
        )
        self.assertEqual(
            list(rows.values_list("birth_year", flat=True)), [1800, 1900, None]
        )
        rows, count, page, size, errors = post_req(
            EnslaverIdentity.objects.all(),
            None,
            {"order_by": ["birth_year"], "page": 1, "page_size": 2},
            EnslaverIdentity_options,
            auto_prefetch=False,
            paginate=True,
        )
        self.assertEqual(errors, [])
        self.assertEqual((count, page, size), (3, 0, 2))
        self.assertEqual([r.birth_year for r in rows], [1900, 1800])

    def test_blog_list_does_not_leak_drafts(self):
        Post.objects.bulk_create(
            [
                Post(
                    title="Published audit",
                    slug="published-audit",
                    content="<p>public</p>",
                    status=1,
                ),
                Post(
                    title="Draft audit",
                    slug="draft-audit",
                    content="<p>private</p>",
                    status=0,
                ),
            ]
        )
        response = PostList.as_view()(
            authenticated("/blog/", {"page": 1, "page_size": 10})
        )
        self.assertEqual(response.status_code, 200, response.content)
        import json

        payload = json.loads(response.content)
        self.assertEqual(payload["count"], 1)
        self.assertEqual([r["title"] for r in payload["results"]], ["Published audit"])

    def test_saved_search_roundtrip_idempotence_and_cleanup_authorization(self):
        import json

        payload = {
            "endpoint": "voyage",
            "front_end_path": "/voyage/trans-atlantic#table",
            "query": [],
        }
        first = MakeSavedSearch.as_view()(
            authenticated("/common/makesavedsearch/", payload)
        )
        self.assertEqual(first.status_code, 200, first.content)
        first = json.loads(first.content)
        self.assertTrue(first["created"])
        second = json.loads(
            MakeSavedSearch.as_view()(
                authenticated("/common/makesavedsearch/", payload)
            ).content
        )
        self.assertEqual(second, {**first, "created": False})
        self.assertEqual(SavedQuery.objects.count(), 1)
        self.assertEqual(
            SavedQuery.objects.get().front_end_path, payload["front_end_path"]
        )
        path = "/common/usesavedsearch/" + first["id"]
        with override_settings(SAVED_SEARCH_CLEANUP_TOKEN="audit-cleanup-only"):
            denied = UseSavedSearch.as_view()(
                authenticated(path, method="delete"), id=first["id"]
            )
            self.assertEqual(denied.status_code, 403)
            self.assertEqual(SavedQuery.objects.count(), 1)
            request = authenticated(path, method="delete")
            request.META["HTTP_X_VOYAGES_SAVED_SEARCH_CLEANUP"] = "audit-cleanup-only"
            allowed = UseSavedSearch.as_view()(request, id=first["id"])
            self.assertEqual(allowed.status_code, 204)
            self.assertEqual(SavedQuery.objects.count(), 0)


class SerializerCompatibilityAudit(SimpleTestCase):
    def test_crosstab_null_bins_and_list_columns(self):
        request = VoyageCrossTabRequestSerializer(
            data={
                "columns": ["voyage_ship__imputed_nationality__name"],
                "rows": "voyage_dates__imp_arrival_at_port_of_dis_sparsedate__year",
                "value_field": "voyage_slaves_numbers__imp_total_num_slaves_embarked",
                "agg_fn": "sum",
                "binsize": None,
            }
        )
        self.assertTrue(request.is_valid(), request.errors)
        self.assertIsNone(request.validated_data["binsize"])
        self.assertEqual(
            request.validated_data["columns"],
            ["voyage_ship__imputed_nationality__name"],
        )

    def test_historical_arrival_stays_distinct_from_imputed_year(self):
        historical = VoyageSparseDate(year=1801, month=2, day=3)
        imputed = VoyageSparseDate(year=1802)
        dates = VoyageDates(
            first_dis_of_slaves_sparsedate=historical,
            imp_arrival_at_port_of_dis_sparsedate=imputed,
        )
        result = VoyageDatesSerializer(dates).data
        self.assertEqual(
            result["first_dis_of_slaves_sparsedate"]["date_str"], "2,3,1801"
        )
        self.assertEqual(result["imp_arrival_at_port_of_dis_sparsedate"]["year"], 1802)
        missing = VoyageDates(imp_arrival_at_port_of_dis_sparsedate=imputed)
        self.assertIsNone(
            VoyageDatesSerializer(missing).data["first_dis_of_slaves_sparsedate"]
        )
