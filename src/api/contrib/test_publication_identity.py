"""Contribution references use public voyage numbers, not database primary keys."""
from django.test import TestCase

from .models import Publication
from .publication import payload_hash, process_publication
from voyage.models import Voyage, VoyageShip


class PublicationIdentityTests(TestCase):
    def setUp(self):
        self.target = Voyage.objects.create(id=11, voyage_id=900001, dataset=0)
        # A primary-key collision must never redirect a public-ID operation.
        self.decoy = Voyage.objects.create(id=900001, voyage_id=900002, dataset=2)

    def publish(self, *, updates=(), deletions=()):
        changeset = {'updates': list(updates), 'deletions': list(deletions)}
        record = Publication.objects.create(
            key='identity-test', changeset=changeset,
            payload_hash=payload_hash(changeset, []), contribution_ids=[],
        )
        process_publication(record.pk)
        record.refresh_from_db()
        return record

    @staticmethod
    def update(schema, identifier, changes, *, kind='existing'):
        return {'entityRef': {'schema': schema, 'id': identifier, 'type': kind},
                'changes': [{'property': name, 'changed': value, **extra}
                            for name, value, extra in changes]}

    def test_existing_voyage_update_uses_public_id_and_preserves_collision(self):
        record = self.publish(updates=[self.update('Voyage', '900001', [('dataset', 1, {})])])
        self.assertEqual(record.status, 'completed', record.error)
        self.target.refresh_from_db()
        self.decoy.refresh_from_db()
        self.assertEqual(self.target.dataset, 1)
        self.assertEqual(self.decoy.dataset, 2)

    def test_existing_voyage_deletion_uses_public_id_and_preserves_collision(self):
        record = self.publish(deletions=[{'entityRef': {'schema': 'Voyage', 'id': '900001', 'type': 'existing'}}])
        self.assertEqual(record.status, 'completed', record.error)
        self.assertFalse(Voyage.objects.filter(pk=self.target.pk).exists())
        self.assertTrue(Voyage.objects.filter(pk=self.decoy.pk, voyage_id=900002).exists())

    def test_new_child_resolves_existing_voyage_public_id(self):
        record = self.publish(updates=[self.update('VoyageShip', 'new-ship', [
            ('voyage_id', '900001', {'isForeignKey': True}), ('ship_name', 'Identity fixture', {}),
        ], kind='new')])
        self.assertEqual(record.status, 'completed', record.error)
        self.assertEqual(VoyageShip.objects.get().voyage_id, self.target.pk)
        self.assertFalse(VoyageShip.objects.filter(voyage=self.decoy).exists())

    def test_existing_child_uses_its_database_id_and_resolves_voyage_public_id(self):
        ship = VoyageShip.objects.create(id=31, voyage=self.decoy, ship_name='Before')
        record = self.publish(updates=[self.update('VoyageShip', str(ship.pk), [
            ('voyage_id', '900001', {'isForeignKey': True}), ('ship_name', 'After', {}),
        ])])
        self.assertEqual(record.status, 'completed', record.error)
        ship.refresh_from_db()
        self.assertEqual((ship.voyage_id, ship.ship_name), (self.target.pk, 'After'))
        self.assertEqual(VoyageShip.objects.count(), 1)

    def test_missing_public_voyage_update_does_not_fall_back_to_database_id(self):
        record = self.publish(updates=[self.update('Voyage', str(self.target.pk), [('dataset', 1, {})])])
        self.assertEqual(record.status, 'failed')
        self.target.refresh_from_db()
        self.decoy.refresh_from_db()
        self.assertEqual((self.target.dataset, self.decoy.dataset), (0, 2))

    def test_missing_public_voyage_foreign_key_rolls_back_instead_of_using_database_id(self):
        record = self.publish(updates=[self.update('VoyageShip', 'new-ship', [
            ('voyage_id', str(self.target.pk), {'isForeignKey': True}),
        ], kind='new')])
        self.assertEqual(record.status, 'failed')
        self.assertFalse(VoyageShip.objects.exists())

    def test_new_voyage_temporary_reference_resolves_to_created_database_id(self):
        record = self.publish(updates=[
            self.update('Voyage', 'temporary-voyage', [('voyage_id', 900003, {}), ('dataset', 0, {})], kind='new'),
            self.update('VoyageShip', 'temporary-ship', [('voyage_id', 'temporary-voyage', {'isForeignKey': True})], kind='new'),
        ])
        self.assertEqual(record.status, 'completed', record.error)
        created = Voyage.objects.get(voyage_id=900003)
        self.assertNotEqual(created.pk, created.voyage_id)
        self.assertEqual(VoyageShip.objects.get().voyage_id, created.pk)
        self.assertEqual(record.result['id_mappings']['temporary-voyage'], created.pk)
