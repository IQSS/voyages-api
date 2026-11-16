import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIRequestFactory

from common.views import Schemas
from past.views import EnslavedList, EnslaverList
from voyage.views import VoyageList


class PublicOptionSchemas(SimpleTestCase):
    def test_public_names_describe_actual_list_fields_in_flat_and_nested_forms(self):
        document = SchemaGenerator(patterns=[
            path("voyage/", VoyageList.as_view()),
            path("past/enslaved/", EnslavedList.as_view()),
            path("past/enslaver/", EnslaverList.as_view()),
        ]).get_schema(public=True)
        fields = {
            "Voyage": ("voyage_ship", "ship_name"),
            "Enslaved": ("post_disembark_location", "name"),
            "Enslaver": ("principal_location", "name"),
            "EnslaverIdentity": ("principal_location", "name"),
        }
        # Only the HTTP boundary between this view and the OpenAPI document is mocked.
        with patch("common.reqs.requests.get", return_value=Mock(text=json.dumps(document))):
            for model, (parent, leaf) in fields.items():
                for flag in ("False/", "True"):
                    with self.subTest(model=model, hierarchical=flag):
                        request = APIRequestFactory().get("/common/schemas/", {
                            "schema_name": model, "hierarchical": flag,
                        })
                        response = Schemas.as_view()(request)
                        self.assertEqual(response.status_code, 200)
                        options = json.loads(response.content)
                        field = options[parent][leaf] if flag == "True" else options[parent + "__" + leaf]
                        self.assertEqual(field["type"], "string")
                        self.assertIsInstance(field["many"], bool)
                        self.assertEqual(options["connections_count"]["type"], "integer")
