# Contribution API

The contribution service calls these endpoints inside the existing Django app:

- `POST /contrib/data`: batched queries against the contribution schema's table and column allowlist. Filters support `equals` and `in`; relation traversal and arbitrary Django models are rejected.
- `POST /contrib/publish_batch`: submit `{key, changeset, contribution_ids}`. A new or pending submission returns HTTP 202. Reusing a key with different input returns HTTP 409. A completed retry returns its original result and `id_mappings`.
- `GET /contrib/publication_status/<key>`: retrieve pending, completed, or failed status. Missing keys return HTTP 404; failed publications return HTTP 400.

All three require `Authorization: Bearer <CONTRIB_SERVICE_TOKEN>`. Set the same
dedicated secret in the Node and Django services. The browser API token cannot
authorize these endpoints. Missing configuration returns HTTP 503 and invalid
credentials return HTTP 401. Never put the service secret in frontend config.

`GET /contrib/location_tree` uses the existing Django API authentication for
browser requests.

Run the normal Django migrations before starting the candidate. Migration
`contrib.0001_initial` adds `contrib_publication`. Publication records persist
the key, input hash, payload, status, and result in MariaDB. A row lock excludes
concurrent workers, and the completed record commits in the same transaction as
the application writes. A lost response therefore cannot duplicate committed
writes. An interrupted transaction remains pending and resumes on the next
submission or status poll. A failed changeset rolls back and retains its failure;
corrected input needs a new key. These records have no automatic expiry.

New voyages retain separate database primary keys and public `voyage_id` values.
Consumers use the returned database ID mapping for subsequent changes.
Source dates use the `SourceDate` schema and `document_docsparsedate` table.
Temporary foreign-key references must point to the model declared by Django;
a voyage-date row cannot be used as a source date.

## Tests

From the repository root, with Django and Django REST Framework installed:

```sh
PYTHONPATH=src/api python -m django test contrib --settings=contrib.test_settings
PYTHONPATH=src/api python -m django makemigrations contrib --check --dry-run --settings=contrib.test_settings
```

The default test database is temporary SQLite. Set `CONTRIB_TEST_DB_PORT` and
`CONTRIB_TEST_DB_PASSWORD` to exercise MariaDB transaction and concurrency tests;
`CONTRIB_TEST_DB_HOST` defaults to `127.0.0.1`. The database must be disposable:
Django creates and drops its test database. No service credentials or live data
are required. The generated changeset fixtures are documented in `testdata/`.
