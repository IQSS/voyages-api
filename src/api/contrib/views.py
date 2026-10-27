"""
This module provides APIs that are used by the Contribute Application (backend
and frontend).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Type, Union, Set
from collections import defaultdict, deque
from django.apps import apps
from django.db import transaction
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q, Model
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import models
from geo.common import GeoTreeFilter
import json
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .auth import service_required
from .publication import publish_batch, publication_status

# Type definitions to match the TypeScript interface
NonNullFieldValue = Union[str, int, float, bool]
BaseFieldValue = Optional[NonNullFieldValue]
ResolvedEntityData = Dict[str, BaseFieldValue]

logger = logging.getLogger(__name__)

class DataFilter:
    """Represents a filter condition on a field."""

    def __init__(self, field: str, value: Union[NonNullFieldValue, List[NonNullFieldValue]], operator: str = "equals"):
        if operator not in ('equals', 'in'):
            raise ValueError('Only equals and in filters are supported')
        if operator == 'in' and not isinstance(value, list):
            raise ValueError('An in filter requires a list')
        if operator == 'equals' and isinstance(value, (dict, list)):
            raise ValueError('An equals filter requires a scalar')
        if isinstance(value, dict) or (isinstance(value, list) and any(isinstance(v, (dict, list)) for v in value)):
            raise ValueError('Filter values must be scalar')
        self.field = field
        self.value = value
        self.operator = operator

    def to_q(self) -> Q:
        """Convert the filter to a Django Q object."""
        if self.operator == "in":
            return Q(**{f"{self.field}__in": self.value})
        # Default to equals
        return Q(**{self.field: self.value})

class DataQuery:
    """Represents a query on a specific model with filters."""

    def __init__(self, model: str, filters: List[DataFilter]):
        self.model = model
        self.filters = filters

    def get_model_class(self) -> Model:
        """Get the Django model class from the model name."""
        for model in set(_schemaToModel.values()):
            if model._meta.db_table == self.model:
                return model
        raise ValueError(f"Model {self.model} is not available for contribution queries")

    def execute(self, fields: List[str]) -> List[ResolvedEntityData]:
        """Execute the query and return the results."""
        model_class = self.get_model_class()
        allowed_fields = {name for f in model_class._meta.fields for name in (f.name, f.attname)}
        if not isinstance(fields, list) or not fields or any(not isinstance(f, str) or f not in allowed_fields for f in fields):
            raise ValueError('Query fields must be named model columns')
        if any(not isinstance(f.field, str) or f.field not in allowed_fields for f in self.filters):
            raise ValueError('Filter fields must be named model columns')

        # Build the filter query
        query = Q()
        for filter_obj in self.filters:
            query &= filter_obj.to_q()

        return list(model_class.objects.filter(query).values(*fields))

class DataResolver:
    """Resolver for a single data query."""

    @staticmethod
    def fetch(input_data: Dict[str, Any]) -> List[ResolvedEntityData]:
        """Fetch data based on the input query."""
        if not isinstance(input_data, dict) or not isinstance(input_data.get('query'), dict):
            raise ValueError('Each query requires a query object and fields')
        if not isinstance(input_data['query'].get('model'), str) or not isinstance(input_data['query'].get('filter'), list):
            raise ValueError('Each query requires a model and filter list')
        if any(not isinstance(f, dict) for f in input_data['query']['filter']):
            raise ValueError('Each filter must be an object')
        query = DataQuery(
            model=input_data["query"]["model"],
            filters=[
                DataFilter(
                    field=filter_obj["field"],
                    value=filter_obj["value"],
                    operator=filter_obj.get("operator", "equals")
                )
                for filter_obj in input_data["query"]["filter"]
            ]
        )
        return query.execute(input_data["fields"])


class BatchDataResolver:
    """Resolver for multiple data queries in one batch."""

    @staticmethod
    def fetchBatch(batch: Dict[str, Dict[str, Any]]) -> Dict[str, List[ResolvedEntityData]]:
        """Fetch multiple queries serially and return results keyed by query ID."""
        results = {}
        for key, input_data in batch.items():
            results[key] = DataResolver.fetch(input_data)
        return results

@csrf_exempt
@service_required
@require_POST
def batch_data_api(request):
    """API endpoint that handles batch data requests."""
    try:
        # Parse the request body
        batch_data = json.loads(request.body)
        # Validate the input
        if not isinstance(batch_data, dict):
            return JsonResponse({"error": "Input must be a dictionary"}, status=400)
        # Execute the batch query
        results = BatchDataResolver.fetchBatch(batch_data)
        # Return the results
        return JsonResponse(results, safe=False)

    except (ValueError, TypeError, KeyError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def location_tree(_):
    return JsonResponse(GeoTreeFilter(select_all=True), safe=False)

_schemaToDbTable: Dict[str, str] = {
  'VoyageSparseDate': 'voyage_voyagesparsedate',
  'SourceDate': 'document_docsparsedate',
  'Nationality': 'voyage_nationality',
  'TonType': 'voyage_tontype',
  'RigOfVessel': 'voyage_rigofvessel',
  'Location': 'geo_location',
  'VoyageShip': 'voyage_voyageship',
  'VoyageItinerary': 'voyage_voyageitinerary',
  'VoyageSlaveNumbers': 'voyage_voyageslavesnumbers',
  'VoyageDates': 'voyage_voyagedates',
  'VoyageGrouping': 'voyage_voyagegroupings',
  'AfricanInfo': 'voyage_africaninfo',
  'VoyageAfricanInfoConnectionSchema': 'voyage_voyage_african_info',
  'CargoUnit': 'voyage_cargounit',
  'CargoType': 'voyage_cargotype',
  'VoyageCargoConnectionSchema': 'voyage_voyagecargoconnection',
  'ParticularOutcome': 'voyage_particularoutcome',
  'SlavesOutcome': 'voyage_slavesoutcome',
  'VesselOutcomeSchema': 'voyage_vesselcapturedoutcome',
  'OwnerOutcome': 'voyage_owneroutcome',
  'Resistance': 'voyage_resistance',
  'VoyageOutcome': 'voyage_voyageoutcome',
  'VoyageCrew': 'voyage_voyagecrew',
  'EnslaverAlias': 'past_enslaveralias',
  'Enslaver': 'past_enslaveridentity',
  'EnslaverAliasWithFK': 'past_enslaveralias',
  'EnslaverAliasWithIdentity': 'past_enslaveralias',
  'EnslavementRelationType': 'past_enslavementrelationtype',
  'EnslaverRole': 'past_enslaverrole',
  'EnslaverRelationRoleConn': 'past_enslaverinrelation_roles',
  'EnslaverInRelation': 'past_enslaverinrelation',
  'Enslaved': 'past_enslaved',
  'LanguageGroup': 'past_languagegroup',
  'EnslavedInRelation': 'past_enslavedinrelation',
  'EnslavementRelation': 'past_enslavementrelation',
  'Voyage Source Type': 'document_sourcetype',
  'Voyage Source Short Reference': 'document_shortref',
  'Voyage Source': 'document_source',
  'Voyage Source Connection': 'document_sourcevoyageconnection',
  'Voyage': 'voyage_voyage'
}

_schemaToModel: Dict[str, Type[models.Model]] = {}
for m in apps.get_models(include_auto_created=True):
    for k, v in _schemaToDbTable.items():
        if m._meta.db_table == v:
            _schemaToModel[k] = m
_missing = set()
for k in _schemaToDbTable.keys():
    if k not in _schemaToModel:
        _missing.add(k)
if _missing:
    logger.error(f"Missing model for schema: {list(_missing)}")
else:
    logger.info("All models mapped successfully")


class PublicationStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PublicationTask:
    """Represents a changeset publication task."""
    publication_key: str
    status: PublicationStatus
    contribution_ids: List[str]
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    changeset: Dict = field(default_factory=dict)
    result: Optional[Dict] = None
    error: Optional[str] = None
    id_mappings: Dict[str, Any] = field(default_factory=dict)
    processed: int = 0


def column_attr(model_class: Type[Model], field_name: str) -> str:
    """
    The attribute on `model_class` that holds a column value.

    A change names the column it writes, and for a foreign key that is what
    Django calls `attname` -- `short_ref_id`. Where a change names the relation
    instead, `voyage_groupings` for `voyage_groupings_id`, assigning a primary
    key to it is refused: the relation wants an instance. Asking the model,
    rather than reading the name, answers for both without depending on the
    change to have described itself correctly.

    Unknown and reverse-relation fields are refused before applying changes.
    """
    try:
        field = model_class._meta.get_field(field_name)
    except FieldDoesNotExist:
        field = next((f for f in model_class._meta.fields if f.attname == field_name), None)
    if field is None or not field.concrete:
        raise ValueError(f'Unknown column {field_name}')
    return getattr(field, "attname", field_name)


def validate_changeset(changeset):
    if not isinstance(changeset, dict):
        raise ValueError('changeset must be an object')
    for operation in ('updates', 'deletions'):
        entries = changeset.get(operation, [])
        if not isinstance(entries, list):
            raise ValueError(f'{operation} must be a list')
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get('entityRef'), dict):
                raise ValueError('Each operation requires an entityRef')
            ref = entry['entityRef']
            if not isinstance(ref.get('schema'), str) or ref['schema'] not in _schemaToModel:
                raise ValueError('Unknown contribution schema')
            if not isinstance(ref.get('id'), (str, int)) or isinstance(ref['id'], bool):
                raise ValueError('Entity IDs must be strings or integers')
            if ref.get('type') not in ('new', 'existing'):
                raise ValueError('Entity type must be new or existing')
            if operation == 'deletions' and ref['type'] != 'existing':
                raise ValueError('Only existing entities can be deleted')
            if operation == 'updates':
                changes = entry.get('changes')
                if not isinstance(changes, list):
                    raise ValueError('Each update requires a changes list')
                for change in changes:
                    if not isinstance(change, dict) or not isinstance(change.get('property'), str) or 'changed' not in change:
                        raise ValueError('Each change requires property and changed')
                    column = column_attr(_schemaToModel[ref['schema']], change['property'])
                    if column == _schemaToModel[ref['schema']]._meta.pk.attname:
                        raise ValueError('Publication cannot change database primary keys')


class ChangeSetProcessor:
    """Processes CombinedChangeSet and applies changes to Django ORM."""

    def __init__(self):
        self.temp_id_to_db_id: Dict[str, Any] = {}
        self.new_entity_ids: Set[str] = set()
        self.new_entity_models = {}

    def process_changeset(self, task: PublicationTask) -> Dict[str, Any]:
        """
        Process the entire changeset in a transaction.
        Returns a mapping of temporary IDs to actual database IDs.
        """
        changeset = task.changeset
        validate_changeset(changeset)
        deletions = changeset.get('deletions', [])
        updates = changeset.get('updates', [])
        processed = 0

        def increment_processed():
            nonlocal processed
            processed += 1
            if (processed % 100 == 0):
                logger.info(f"Processed {processed} operations...")

        # Validate no duplicate entity updates and no updates to deleted entities
        self._validate_no_duplicates(deletions, updates)

        # Collect all new entity IDs first
        self.new_entity_ids = {
            update['entityRef']['id']
            for update in updates
            if update['entityRef'].get('type') == 'new'
        }
        for update in updates:
            ref = update['entityRef']
            if ref['type'] == 'new':
                if ref['id'] in self.new_entity_models:
                    raise ValueError('New entity temporary IDs must be unique')
                self.new_entity_models[ref['id']] = self._get_model_class(ref['schema'])

        # Separate new and existing entity updates
        new_updates = [u for u in updates if u['entityRef'].get('type') == 'new']
        existing_updates = [u for u in updates if u['entityRef'].get('type') != 'new']

        # Sort new entities by FK dependencies
        sorted_new_updates = self._topological_sort(new_updates)

        with transaction.atomic():
            # Process deletions first
            for deletion in deletions:
                increment_processed()
                self._process_deletion(deletion)

            # Process new entities in dependency order
            for update in sorted_new_updates:
                logger.debug(json.dumps(update))
                increment_processed()
                self._process_new_entity(update)

            # Process existing entity updates
            for update in existing_updates:
                increment_processed()
                self._process_existing_entity(update)

        task.processed = processed
        return self.temp_id_to_db_id

    def _validate_no_duplicates(self, deletions: List[Dict], updates: List[Dict]):
        """Validate that each entity is updated at most once and deleted entities aren't updated."""
        updated_entities = set()
        deleted_entities = set()

        # Collect deleted entity references
        for deletion in deletions:
            entity_key = self._get_entity_key(deletion['entityRef'])
            deleted_entities.add(entity_key)

        # Check for duplicate updates and updates to deleted entities
        for update in updates:
            entity_key = self._get_entity_key(update['entityRef'])

            if entity_key in deleted_entities:
                raise ValueError(f"Cannot update deleted entity: {entity_key}")

            if entity_key in updated_entities:
                raise ValueError(f"Duplicate update for entity: {entity_key}")

            updated_entities.add(entity_key)

    def _get_entity_key(self, entity_ref: Dict) -> str:
        """Create a unique key for an entity reference."""
        return f"{entity_ref['schema']}:{entity_ref['id']}"

    def _topological_sort(self, new_updates: List[Dict]) -> List[Dict]:
        """
        Sort new entities based on foreign key dependencies.
        Returns sorted list or raises ValueError if cycle detected.
        """
        # Build dependency graph
        graph = defaultdict(list)  # entity_id -> list of entities that depend on it
        in_degree = defaultdict(int)  # entity_id -> number of dependencies
        entity_map = {}  # entity_id -> update dict

        for update in new_updates:
            entity_id = update['entityRef']['id']
            entity_map[entity_id] = update

            # Find FK dependencies to other new entities
            for change in update['changes']:
                if change.get('isForeignKey') and change.get('changed'):
                    fk_value = change['changed']
                    # Check if FK points to a new entity (using set membership)
                    if fk_value in self.new_entity_ids:
                        graph[fk_value].append(entity_id)
                        in_degree[entity_id] += 1

        # Initialize queue with entities that have no dependencies
        queue = deque()
        for update in new_updates:
            entity_id = update['entityRef']['id']
            if in_degree[entity_id] == 0:
                queue.append(entity_id)

        # Process queue (Kahn's algorithm)
        sorted_ids = []
        while queue:
            current_id = queue.popleft()
            sorted_ids.append(current_id)

            # Reduce in-degree for dependent entities
            for dependent_id in graph[current_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        # Check for cycles
        if len(sorted_ids) != len(new_updates):
            raise ValueError("Circular dependency detected in new entities")

        # Return updates in sorted order
        return [entity_map[entity_id] for entity_id in sorted_ids]

    def _process_deletion(self, deletion: Dict):
        """Process a deletion operation."""
        entity_ref = deletion['entityRef']
        model_class = self._get_model_class(entity_ref['schema'])

        try:
            obj = model_class.objects.get(pk=entity_ref['id'])
            obj.delete()
            logger.debug(f"Deleted {entity_ref['schema']} with id {entity_ref['id']}")
        except model_class.DoesNotExist:
            logger.warning(f"Entity {entity_ref['schema']} with id {entity_ref['id']} not found for deletion")

    def _process_new_entity(self, update: Dict):
        """Process creation of a new entity."""
        entity_ref = update['entityRef']
        model_class = self._get_model_class(entity_ref['schema'])

        # Prepare field values
        field_values = {}
        for change in update['changes']:
            field_name = column_attr(model_class, change['property'])
            value = self._resolve_value(model_class, field_name, change)

            field_values[field_name] = value

        # Create the entity - let Django handle field validation
        obj = model_class(**field_values)
        obj.save()

        # Store the mapping from temporary ID to actual database ID
        self.temp_id_to_db_id[entity_ref['id']] = obj.pk

        logger.debug(f"Created {entity_ref['schema']} with temp id {entity_ref['id']} -> db id {obj.pk}")

    def _process_existing_entity(self, update: Dict):
        """Process update of an existing entity."""
        entity_ref = update['entityRef']
        model_class = self._get_model_class(entity_ref['schema'])

        try:
            obj = model_class.objects.get(pk=entity_ref['id'])

            # Apply changes
            for change in update['changes']:
                field_name = column_attr(model_class, change['property'])
                value = self._resolve_value(model_class, field_name, change)

                setattr(obj, field_name, value)

            obj.save()
            logger.debug(f"Updated {entity_ref['schema']} with id {entity_ref['id']}")

        except model_class.DoesNotExist:
            raise ValueError(f"Entity {entity_ref['schema']} with id {entity_ref['id']} not found for update")

    def _resolve_value(self, model_class, column, change):
        value = change['changed']
        field = next(f for f in model_class._meta.fields if f.attname == column)
        if change.get('isForeignKey') and not field.is_relation:
            raise ValueError(f'{column} is not a foreign key')
        if field.is_relation and value is not None and value in self.new_entity_ids:
            if self.new_entity_models[value] is not field.related_model:
                raise ValueError(f'Foreign key {column} references the wrong model')
            if value not in self.temp_id_to_db_id:
                raise ValueError(f'Foreign key references unprocessed entity: {value}')
            value = self.temp_id_to_db_id[value]
        return value

    def _get_model_class(self, schema_name: str):
        """Get Django model class from schema name."""
        # Try to get model from any installed app
        if schema_name not in _schemaToModel:
            raise ValueError(f"Model {schema_name} not found in any app")
        return _schemaToModel[schema_name]
