# Changeset fixtures

`changesets.json` holds the payloads `contrib/tests.py` publishes. It is
generated, not written.

## Why generated

A contribution's payload is built from the Contribute app's schemas, by the
same package the app ships. Typing one by hand here would mean typing the
field names someone believed in — and believing the wrong one is precisely
the failure worth catching. A property naming a Django relation instead of
its column reads correctly and fails on write; a hand-written fixture would
have carried the column name and proved nothing.

So the fixtures come from `@slavevoyages/voyages-contribute` at a pinned
version, recorded in the file as `generatedBy`. What they contain is what a
client of that version sends.

## Regenerating

After the Contribute schemas change:

```sh
cd generator
export GITHUB_TOKEN=...        # needs read:packages
npm install                    # bump the dependency first to move versions
npm run generate
```

Review the diff. A changed field name there is a change in what clients send,
which is worth reading rather than waving through. The tests stay in Python;
nothing about running them needs Node.

## Shape

- `generatedBy` — the package release the changesets were built from.
- `seed` — rows the changesets reference, as `{table, pk, fields}`. The test
  creates them before publishing; tables are resolved to models by
  `_meta.db_table`.
- `steps` — published in order. A step names a row an earlier step created by
  the temporary id that created it, and the test substitutes the database ids
  publication returned.

## Known gap

The source `Date` is left out: the schema links it to
`voyage_voyagesparsedate` while the column references
`document_docsparsedate`, so any value fails the foreign key. Tracked as
SlaveVoyages/voyages-contribute#17.
