import { useState } from "react"
import {
  useAddDistance, useDeleteDistance, useUpdateDistance,
  type DistanceAdmin, type DistanceChanges, type OrganizerEvent,
} from "@/api/organizer"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { formatKES } from "@/lib/format"
import { DistanceFields } from "./DistanceFields"
import { draftError, emptyDraft, toDraft, toInput, type DistanceDraft } from "./distanceDraft"

function DistanceRow({ eventId, d }: { eventId: string; d: DistanceAdmin }) {
  const update = useUpdateDistance(eventId)
  const remove = useDeleteDistance(eventId)
  const [draft, setDraft] = useState<DistanceDraft>(() => toDraft(d))
  const [localError, setLocalError] = useState<string | null>(null)

  const taken = d.confirmed + d.held
  const dirty = JSON.stringify(draft) !== JSON.stringify(toDraft(d))

  function save() {
    const problem = draftError(draft)
    if (problem) return setLocalError(problem)
    setLocalError(null)
    const changes: DistanceChanges = {}
    if (draft.name.trim() !== d.name) changes.name = draft.name.trim()
    if (Number(draft.km) !== Number(d.km)) changes.km = Number(draft.km)
    if (Number(draft.fee) !== Number(d.fee)) changes.fee = Number(draft.fee)
    if (Number(draft.capacity) !== d.capacity) changes.capacity = Number(draft.capacity)
    if (Number(draft.min_age) !== d.min_age) changes.min_age = Number(draft.min_age)
    update.mutate({ distanceId: d.id, changes })
  }

  function onDelete() {
    if (window.confirm(`Delete the ${d.name} distance?`)) remove.mutate(d.id)
  }

  const error = localError ?? update.error?.message ?? remove.error?.message

  return (
    <Card>
      <CardContent className="space-y-3 pt-6">
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
          <span>
            {d.confirmed} confirmed · {d.held} awaiting payment · {d.spots_left} spots left · now {formatKES(d.fee)}
          </span>
        </div>
        <DistanceFields
          idPrefix={`d-${d.id}`}
          value={draft}
          onChange={setDraft}
          lockBasics={taken > 0}
          minCapacity={Math.max(taken, 1)}
        />
        {taken > 0 && (
          <p className="text-xs text-muted-foreground">
            Name, distance and minimum age are locked because runners have registered. Fee changes apply to new
            registrations only.
          </p>
        )}
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        <div className="flex gap-2">
          <Button size="sm" onClick={save} disabled={!dirty || update.isPending}>
            {update.isPending ? "Saving…" : "Save"}
          </Button>
          <Button size="sm" variant="outline" onClick={onDelete} disabled={remove.isPending}>
            Delete
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function AddDistance({ eventId }: { eventId: string }) {
  const add = useAddDistance(eventId)
  const [draft, setDraft] = useState<DistanceDraft>(emptyDraft)
  const [localError, setLocalError] = useState<string | null>(null)

  function onAdd() {
    const problem = draftError(draft)
    if (problem) return setLocalError(problem)
    setLocalError(null)
    add.mutate(toInput(draft), { onSuccess: () => setDraft(emptyDraft()) })
  }

  const error = localError ?? add.error?.message
  return (
    <Card>
      <CardContent className="space-y-3 pt-6">
        <h3 className="font-medium">Add a distance</h3>
        <DistanceFields idPrefix="new-distance" value={draft} onChange={setDraft} />
        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        <Button size="sm" onClick={onAdd} disabled={add.isPending}>
          {add.isPending ? "Adding…" : "Add distance"}
        </Button>
      </CardContent>
    </Card>
  )
}

export function DistanceManager({ event }: { event: OrganizerEvent }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">Distances</h2>
      {event.distances.length === 0 && (
        <p className="text-sm text-muted-foreground">No distances yet. Add one before publishing.</p>
      )}
      {event.distances.map((d) => (
        // The key includes the saved values, so a row resets to the server's numbers after each save.
        <DistanceRow key={`${d.id}-${d.name}-${d.km}-${d.fee}-${d.capacity}-${d.min_age}`} eventId={event.id} d={d} />
      ))}
      <AddDistance eventId={event.id} />
    </section>
  )
}