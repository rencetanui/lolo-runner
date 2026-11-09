import { useState } from "react"
import { Link, useParams } from "react-router-dom"
import { useEvent } from "@/api/events"
import { useAvailability } from "@/api/registrations"
import { RegistrationBadge } from "@/components/RegistrationBadge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDate, formatKES, formatKm, formatTime, registrationState } from "@/lib/format"
import { shareEvent } from "@/lib/share"

export default function EventDetailPage() {
  const { id = "" } = useParams()
  const { data: event, isLoading, error } = useEvent(id)
  const { data: availability } = useAvailability(id, event?.status === "published")
  const [shareNote, setShareNote] = useState<string | null>(null)

  if (isLoading) return <Skeleton className="m-4 mx-auto h-64 max-w-3xl" />

  if (error || !event)
    return (
      <main className="mx-auto max-w-3xl p-4">
        <Alert variant="destructive">
          <AlertTitle>{error?.message ?? "Event not found"}</AlertTitle>
          <AlertDescription>
            <Link to="/" className="underline">Back to all races</Link>
          </AlertDescription>
        </Alert>
      </main>
    )

  const isOpen = event.status === "published" && registrationState(event.registration_opens, event.registration_closes) === "open"
  const spotsLeft = (distanceId: string) => availability?.find((a) => a.distance_id === distanceId)?.spots_left

  async function onShare() {
    const result = await shareEvent(event!.id, event!.name)
    setShareNote(result === "copied" ? "Link copied" : result === "failed" ? "Couldn't copy the link" : null)
  }

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      <Link to="/" className="text-sm text-muted-foreground hover:underline">← All races</Link>

      {event.banner_url && (
        <img src={event.banner_url} alt="" className="max-h-72 w-full rounded-lg object-cover" />
      )}

      <header className="space-y-2">
        <h1 className="text-2xl font-bold sm:text-3xl">{event.name}</h1>
        <p className="text-muted-foreground">{formatDate(event.event_date)} · {event.location}</p>
        <div className="flex flex-wrap items-center gap-3">
          {event.status === "published" && (
            <RegistrationBadge opens={event.registration_opens} closes={event.registration_closes} />
          )}
          <Button variant="outline" size="sm" onClick={onShare}>Share</Button>
          {shareNote && <span className="text-sm text-muted-foreground">{shareNote}</span>}
        </div>
      </header>

      {event.status === "cancelled" && (
        <Alert variant="destructive">
          <AlertTitle>This event has been cancelled</AlertTitle>
          <AlertDescription>{event.cancellation_reason}</AlertDescription>
        </Alert>
      )}
      {event.status === "published" && (
        <p className="text-sm text-muted-foreground">
          {event.refunds_until
            ? `Refunds are available until ${formatDate(event.refunds_until)}.`
            : "Entries are non-refundable."}
        </p>
      )}

      {event.description && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">About this race</h2>
          <p className="whitespace-pre-line text-sm leading-relaxed">{event.description}</p>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Distances</h2>
        {event.distances.map((d) => {
          const left = spotsLeft(d.id)
          const soldOut = left === 0
          return (
            <Card key={d.id}>
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle>{d.name}</CardTitle>
                <span className="font-semibold">{d.fee === "0.00" ? "Free" : formatKES(d.fee)}</span>
              </CardHeader>
              <CardContent className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm text-muted-foreground">
                  {formatKm(d.km)}
                  {d.start_time && ` · Starts ${formatTime(d.start_time)}`}
                  {d.cutoff_minutes ? ` · ${d.cutoff_minutes} min cut-off` : ""}
                  {` · Minimum age ${d.min_age}`}
                  {left !== undefined && !soldOut && ` · ${left} spots left`}
                </div>
                {isOpen && !soldOut ? (
                  <Link to={`/events/${event.id}/register?distance=${d.id}`} className={buttonVariants({ size: "sm" })}>
                    Register
                  </Link>
                ) : (
                  <Button size="sm" disabled>{soldOut ? "Sold out" : "Unavailable"}</Button>
                )}
              </CardContent>
            </Card>
          )
        })}
      </section>

      {(event.venue_details || event.map_url) && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">Getting there</h2>
          {event.venue_details && <p className="whitespace-pre-line text-sm leading-relaxed">{event.venue_details}</p>}
          {event.map_url && (
            <a href={event.map_url} target="_blank" rel="noopener noreferrer" className="text-sm underline">
              Open in maps
            </a>
          )}
        </section>
      )}

      {(event.contact_email || event.contact_phone) && (
        <section className="space-y-1">
          <h2 className="text-lg font-semibold">Questions?</h2>
          <p className="text-sm text-muted-foreground">Contact the organizers.</p>
          <div className="flex flex-wrap gap-4 text-sm">
            {event.contact_email && <a className="underline" href={`mailto:${event.contact_email}`}>{event.contact_email}</a>}
            {event.contact_phone && <a className="underline" href={`tel:${event.contact_phone}`}>{event.contact_phone}</a>}
          </div>
        </section>
      )}
    </main>
  )
}