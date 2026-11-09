import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useCreateEvent } from "@/api/organizer"
import { DistanceFields } from "@/components/organizer/DistanceFields"
import { draftError, emptyDraft, toInput, type DistanceDraft } from "@/components/organizer/distanceDraft"
import {
  detailsPayload, EventDetailsFields, detailsError, emptyDetails, type EventDetails,
} from "@/components/organizer/EventDetailsFields"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"


export default function OrganizerNewEventPage() {
  const navigate = useNavigate()
  const create = useCreateEvent()
  const [details, setDetails] = useState<EventDetails>(emptyDetails)
  const [distances, setDistances] = useState<DistanceDraft[]>([emptyDraft()])
  const [localError, setLocalError] = useState<string | null>(null)

  const setDistance = (i: number) => (d: DistanceDraft) =>
    setDistances((list) => list.map((x, j) => (j === i ? d : x)))

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    const problem = detailsError(details) ?? distances.map(draftError).find(Boolean) ?? null
    if (problem) return setLocalError(problem)
    setLocalError(null)
    create.mutate(
      { ...detailsPayload(details), distances: distances.map(toInput) },
      { onSuccess: (event) => navigate(`/organizer/events/${event.id}`) },
    )
  }

  const error = localError ?? create.error?.message

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <div>
        <Link to="/organizer" className="text-sm text-muted-foreground hover:underline">← My events</Link>
        <h1 className="mt-2 text-2xl font-bold sm:text-3xl">New event</h1>
      </div>

      <form onSubmit={onSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
            <CardDescription>The event is saved as a draft. Runners can't see it until you publish.</CardDescription>
          </CardHeader>
          <CardContent><EventDetailsFields value={details} onChange={setDetails} /></CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Distances</CardTitle>
            <CardDescription>Fees are in whole Kenya shillings. Use 0 for a free distance.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {distances.map((d, i) => (
              <div key={i} className="space-y-2 rounded-md border p-3">
                <DistanceFields idPrefix={`nd-${i}`} value={d} onChange={setDistance(i)} />
                {distances.length > 1 && (
                  <Button type="button" variant="outline" size="sm"
                    onClick={() => setDistances((list) => list.filter((_, j) => j !== i))}>
                    Remove
                  </Button>
                )}
              </div>
            ))}
            <Button type="button" variant="outline" size="sm"
              onClick={() => setDistances((list) => [...list, emptyDraft()])}>
              Add another distance
            </Button>
          </CardContent>
        </Card>

        {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
        <Button type="submit" size="lg" disabled={create.isPending}>
          {create.isPending ? "Saving…" : "Save draft"}
        </Button>
      </form>
    </main>
  )
}