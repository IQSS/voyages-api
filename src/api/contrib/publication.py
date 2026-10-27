"""Publication jobs whose result and application writes share one transaction.

Pending jobs are retried by submission or status polling. A worker interrupted
before commit leaves the job pending; a response lost after commit returns the
stored result. Redis expiry and pod replacement cannot repeat committed writes.
"""
import hashlib
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from django.db import DatabaseError, OperationalError, close_old_connections, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .auth import service_required
from .models import Publication

logger = logging.getLogger(__name__)
_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix='contribution-publication')
_inflight = set()
_inflight_lock = threading.Lock()


def payload_hash(changeset, contribution_ids):
    encoded = json.dumps(
        {'changeset': changeset, 'contribution_ids': contribution_ids},
        sort_keys=True, separators=(',', ':'), allow_nan=False,
    ).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def process_publication(key):
    from .views import ChangeSetProcessor, PublicationTask

    # The row lock prevents another pod or HTTP retry from publishing twice.
    # Processing is deliberately not committed separately from the changes.
    with transaction.atomic():
        record = Publication.objects.select_for_update(nowait=True).get(pk=key)
        if record.status != 'pending':
            return
        task = PublicationTask(
            publication_key=record.key, status='processing',
            changeset=record.changeset, contribution_ids=record.contribution_ids,
            created_at=record.created_at,
        )
        try:
            with transaction.atomic():
                mappings = ChangeSetProcessor().process_changeset(task)
            record.status = 'completed'
            record.processed = task.processed
            record.result = {
                'success': True, 'id_mappings': mappings,
                'message': 'Changeset processed successfully',
            }
        except OperationalError:
            # Connection failure, deadlock, or lock timeout: the whole attempt
            # rolls back and remains pending for a later request to retry.
            raise
        except Exception as exc:
            logger.exception('Publication failed for %s', key)
            record.status = 'failed'
            record.error = str(exc) if isinstance(exc, ValueError) else 'Publication changes could not be applied'
        record.completed_at = timezone.now()
        record.save()


def _run_worker(key):
    close_old_connections()
    try:
        process_publication(key)
    except DatabaseError:
        # A worker already holds the row lock, or the database is temporarily
        # unavailable. Retain pending state and retry through the next poll.
        logger.warning('Publication worker will retry %s', key)
    finally:
        close_old_connections()
        with _inflight_lock:
            _inflight.discard(key)


def schedule_publication(key):
    with _inflight_lock:
        if key in _inflight:
            return
        _inflight.add(key)
    try:
        _workers.submit(_run_worker, key)
    except RuntimeError:
        with _inflight_lock:
            _inflight.discard(key)


def _response(record):
    body = {
        'publication_key': record.key, 'status': record.status,
        'contribution_ids': record.contribution_ids,
        'processed_operations': record.processed,
        'created_at': record.created_at.isoformat(),
        'updated_at': record.updated_at.isoformat(),
    }
    if record.completed_at:
        body['completed_at'] = record.completed_at.isoformat()
    if record.status == 'completed':
        body.update(record.result)
    elif record.status == 'failed':
        body['error'] = record.error
    return JsonResponse(body, status=400 if record.status == 'failed' else 200)


@csrf_exempt
@service_required
@require_POST
def publish_batch(request):
    from .views import validate_changeset

    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError('Publication must be an object')
        key = data.get('key')
        if not isinstance(key, str) or not key.strip() or len(key) > 200:
            raise ValueError('An idempotency key of at most 200 characters is required')
        changeset = data.get('changeset')
        validate_changeset(changeset)
        contribution_ids = data.get('contribution_ids', [])
        if not isinstance(contribution_ids, list) or any(not isinstance(value, str) for value in contribution_ids):
            raise ValueError('contribution_ids must be a list of strings')
        digest = payload_hash(changeset, contribution_ids)
    except (ValueError, TypeError, KeyError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    record, _ = Publication.objects.get_or_create(
        key=key, defaults={
            'payload_hash': digest, 'changeset': changeset,
            'contribution_ids': contribution_ids,
        },
    )
    if record.payload_hash != digest:
        return JsonResponse({'error': 'Idempotency key already belongs to a different payload'}, status=409)
    if record.status != 'pending':
        return _response(record)
    transaction.on_commit(lambda: schedule_publication(key))
    return JsonResponse({'status': 'accepted', 'publication_key': key}, status=202)


@service_required
@require_GET
def publication_status(request, publication_key):
    try:
        record = Publication.objects.get(pk=publication_key)
    except Publication.DoesNotExist:
        return JsonResponse({'error': 'Publication not found'}, status=404)
    if record.status == 'pending':
        transaction.on_commit(lambda: schedule_publication(publication_key))
    return _response(record)
