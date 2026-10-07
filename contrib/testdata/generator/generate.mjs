/**
 * Produces the changesets `contrib/tests.py` replays.
 *
 * The payload a contribution publishes is not hand-written anywhere: the app
 * builds it out of the schemas, through `combineChanges` and
 * `foldCombinedChanges`. A fixture typed by hand would carry whatever field
 * names the person typing believed in, which is exactly the thing worth
 * testing -- a property naming a Django relation instead of its column reads
 * fine and fails on write, and no hand-written fixture would ever have said
 * so. So the fixtures come from the same package the app uses, at a pinned
 * version, and record which one produced them.
 *
 * Run `npm install && npm run generate` after the schemas change. A GitHub
 * token with `read:packages` is needed to reach the registry.
 */
import { readFileSync, writeFileSync } from "node:fs"
import {
  combineChanges,
  foldCombinedChanges,
  materializeNew,
  VoyageSchema,
  VoyageGroupingSchema,
  VoyageCargoConnectionSchema,
  CargoTypeSchema,
  VoyageSourceSchema,
  VoyageSourceConnectionSchema,
  VoyageShortRefSchema
} from "@slavevoyages/voyages-contribute"

const pkg = JSON.parse(
  readFileSync("./node_modules/@slavevoyages/voyages-contribute/package.json")
)

/** A property's uid, which is how a change names what it changes. */
const uid = (schema, label) => {
  const p = schema.properties.find((x) => x.label === label)
  if (p === undefined) {
    throw new Error(`${schema.name} has no property labelled "${label}"`)
  }
  return p.uid
}

/** A reference to a row the fixture asks to have seeded. */
const seeded = []
const seed = (schema, id, fields) => {
  seeded.push({ table: schema.backingTable, pk: id, fields })
  return { entityRef: { type: "existing", schema: schema.name, id }, state: "lazy", data: {} }
}

const direct = (schema, label, changed) => ({
  kind: "direct",
  property: uid(schema, label),
  changed
})
const linked = (schema, label, target) => ({
  kind: "linked",
  property: uid(schema, label),
  changed: target
})

const grouping = seed(VoyageGroupingSchema, 1, { name: "Fixture grouping", value: 1 })
const grouping2 = seed(VoyageGroupingSchema, 2, { name: "Fixture grouping two", value: 2 })
const cargoType = seed(CargoTypeSchema, 1, { name: "Fixture cargo" })
const shortRef = seed(VoyageShortRefSchema, 1, { name: "FIXTURE REF 1" })

const VOYAGE_TEMP_ID = "fixture_voyage_1"

/** A voyage arriving whole: its own fields, a grouping, cargo, and a source. */
const createVoyage = () => {
  const voyage = materializeNew(VoyageSchema, VOYAGE_TEMP_ID)
  const cargo = materializeNew(VoyageCargoConnectionSchema, "fixture_cargo_1")
  const source = materializeNew(VoyageSourceSchema, "fixture_source_1")
  const connection = materializeNew(VoyageSourceConnectionSchema, "fixture_srcconn_1")
  return [
    {
      type: "update",
      entityRef: voyage.entityRef,
      changes: [
        direct(VoyageSchema, "Voyage ID", 900001),
        direct(VoyageSchema, "Dataset", 0),
        // The property this whole exercise is about: a foreign key whose
        // backing field named the relation rather than the column.
        linked(VoyageSchema, "Voyage grouping", grouping),
        {
          kind: "ownedList",
          property: uid(VoyageSchema, "Cargo"),
          removed: [],
          modified: [
            {
              kind: "owned",
              ownedEntity: cargo,
              changes: [
                linked(VoyageCargoConnectionSchema, "Cargo type", cargoType),
                direct(
                  VoyageCargoConnectionSchema,
                  "The amount of cargo according to the unit",
                  7
                )
              ]
            }
          ]
        },
        {
          kind: "ownedList",
          property: uid(VoyageSchema, "Sources"),
          removed: [],
          modified: [
            {
              kind: "owned",
              ownedEntity: connection,
              changes: [
                {
                  kind: "linked",
                  property: uid(VoyageSourceConnectionSchema, "Source"),
                  changed: source,
                  // A source brought into being by the contribution, dated --
                  // the second property that named a relation.
                  // The source's Date is left out: the schema links it to
                  // `voyage_voyagesparsedate` while the column references
                  // `document_docsparsedate`, so any value fails the foreign
                  // key. Tracked as SlaveVoyages/voyages-contribute#17; put it
                  // back here once that is resolved.
                  linkedChanges: [
                    direct(VoyageSourceSchema, "Title", "Fixture source"),
                    linked(VoyageSourceSchema, "Short reference", shortRef)
                  ]
                },
                direct(VoyageSourceConnectionSchema, "Page range", "12-14")
              ]
            }
          ]
        }
      ]
    }
  ]
}

/** The same voyage once published, moved to a different grouping. */
const editVoyage = () => [
  {
    type: "update",
    entityRef: { type: "existing", schema: "Voyage", id: VOYAGE_TEMP_ID },
    changes: [linked(VoyageSchema, "Voyage grouping", grouping2)]
  }
]

/** And cleared again, which is the only value this property ever held before. */
const clearGrouping = () => [
  {
    type: "update",
    entityRef: { type: "existing", schema: "Voyage", id: VOYAGE_TEMP_ID },
    changes: [linked(VoyageSchema, "Voyage grouping", null)]
  }
]

const fold = (changes) => {
  const folded = foldCombinedChanges([combineChanges(changes)])
  const errors = folded.validation.filter((v) => v.kind === "error")
  if (errors.length > 0 || folded.conflicts.length > 0) {
    throw new Error(
      `changeset does not fold cleanly: ${JSON.stringify({ errors, conflicts: folded.conflicts }, null, 2)}`
    )
  }
  return { deletions: folded.deletions, updates: folded.updates }
}

const steps = [
  { name: "create a voyage with a grouping, cargo and a dated source", changeset: fold(createVoyage()) },
  { name: "edit the published voyage", changeset: fold(editVoyage()) },
  { name: "clear the grouping", changeset: fold(clearGrouping()) }
]

const fixture = {
  generatedBy: `${pkg.name}@${pkg.version}`,
  // The temporary ids a step invents are how a later step names the row that
  // step created; the replay substitutes the database ids it was given.
  newEntityTempIds: [VOYAGE_TEMP_ID],
  seed: seeded,
  steps
}

writeFileSync("../changesets.json", JSON.stringify(fixture, null, 2) + "\n")
console.log(
  `wrote ../changesets.json from ${fixture.generatedBy}: ${steps.length} steps, ${seeded.length} seeded rows`
)
