import { Link, useParams } from "react-router-dom"
import { useEvent } from "@/api/events"
import { useAvailability } from "@/api/registrations"
import { RegistrationBadge } from "@/components/RegistrationBadge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDate, formatKES, formatKm, registrationState } from "@/lib/format"

export default function EventDetailPage() {
  const { id = "" } = useParams()
  const { data: event, isLoading, error } = useEvent(id)
  const { data: availability } = useAvailability(id)

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
  const spotsLeft = (distanceId: string) =>
    availability?.find((a) => a.distance_id === distanceId)?.spots_left

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
      <Link to="/" className="text-sm text-muted-foreground hover:underline">← All races</Link>

      <header className="space-y-2">
        <h1 className="text-2xl font-bold sm:text-3xl">{event.name}</h1>
        <p className="text-muted-foreground">
          {formatDate(event.event_date)} · {event.location}
        </p>
        <RegistrationBadge opens={event.registration_opens} closes={event.registration_closes} />
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
                  {formatKm(d.km)} · Minimum age {d.min_age}
                  {left !== undefined && !soldOut && ` · ${left} spots left`}
                </div>
                {isOpen && !soldOut ? (
                  <Link to={`/events/${event.id}/register?distance=${d.id}`} className={buttonVariants({ size: "sm" })}>Register</Link>
                ) : (
                  <Button size="sm" disabled>{soldOut ? "Sold out" : "Unavailable"}</Button>
                )}
              </CardContent>
            </Card>
          )
        })}
      </section>
    </main>
  )
}
