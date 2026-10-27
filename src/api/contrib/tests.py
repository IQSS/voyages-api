"""
Publication, replayed from changesets the Contribute app actually produces.

The payload a contribution publishes is built from the schemas, by the
package the app itself uses -- so a fixture written by hand here would carry
whatever field names the person writing it believed in, and that is the thing
worth testing. A property naming a Django relation instead of its column
reads fine and fails on write, and no hand-typed fixture would ever have said
so.

`testdata/changesets.json` is therefore generated, by
`testdata/generator/generate.mjs`, against a pinned release of the package.
Regenerate it when the schemas move; the tests below stay here.
"""
import json
from pathlib import Path

from django.apps import apps
from django.test import TestCase

from contrib.views import ChangeSetProcessor, PublicationTask
from document.models import Source
from voyage.models import Voyage, VoyageCargoConnection

FIXTURE = Path(__file__).parent / "testdata" / "changesets.json"


def _model_for_table(table):
    for model in apps.get_models(include_auto_created=True):
        if model._meta.db_table == table:
            return model
    raise LookupError("No model backs the table %s" % table)


class ReplayedChangeSetTests(TestCase):
    """Publishes the generated steps in order, against a test database."""

    @classmethod
    def setUpTestData(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def setUp(self):
        for row in self.fixture["seed"]:
            _model_for_table(row["table"]).objects.create(pk=row["pk"], **row["fields"])
        # A step names a row an earlier step created by the temporary id that
        # created it. Publication answers with the database ids it assigned.
        self.resolved = {}

    def _publish(self, step):
        changeset = self._substitute(step["changeset"])
        task = PublicationTask(
            publication_key="test",
            status="pending",
            contribution_ids=[],
            created_at=None,
        )
        task.changeset = changeset
        self.resolved.update(ChangeSetProcessor().process_changeset(task))

    def _substitute(self, changeset):
        """Replace temporary ids with the database ids publication assigned."""
        raw = json.dumps(changeset)
        for temp_id, db_id in self.resolved.items():
            raw = raw.replace('"%s"' % temp_id, json.dumps(db_id))
        return json.loads(raw)

    def _replay(self, upto):
        for step in self.fixture["steps"][: upto + 1]:
            self._publish(step)

    def test_the_fixture_records_which_package_built_it(self):
        # Without it there is no telling which schemas these changesets came
        # from, and a stale fixture passing says nothing about the app.
        self.assertIn("@slavevoyages/voyages-contribute@", self.fixture["generatedBy"])
        self.assertEqual(len(self.fixture["steps"]), 3)

    def test_a_voyage_publishes_whole(self):
        self._replay(0)

        voyage = Voyage.objects.get(voyage_id=900001)
        # The foreign key the app names after the relation rather than the
        # column. Django refuses a primary key on the relation, so this is
        # only reachable if the write path resolves the name to its column.
        self.assertEqual(voyage.voyage_groupings_id, 1)
        self.assertEqual(voyage.dataset, 0)

        cargo = VoyageCargoConnection.objects.get(voyage=voyage)
        self.assertEqual((cargo.cargo_id, cargo.amount), (1, 7))

        source = Source.objects.get(title="Fixture source")
        self.assertEqual(source.short_ref_id, 1)
        self.assertEqual(
            source.source_voyage_connections.first().page_range, "12-14"
        )

    def test_a_published_voyage_can_be_edited(self):
        self._replay(1)
        voyage = Voyage.objects.get(voyage_id=900001)
        self.assertEqual(voyage.voyage_groupings_id, 2)

    def test_the_grouping_can_be_cleared_again(self):
        self._replay(2)
        voyage = Voyage.objects.get(voyage_id=900001)
        self.assertIsNone(voyage.voyage_groupings_id)
