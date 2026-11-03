import { useState } from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"
import { useEvent } from "@/api/events"
import { useProfile } from "@/api/profile"
import { useRegister, useWaiver } from "@/api/registrations"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { ageOn, formatDate, formatKES } from "@/lib/format"

export default function RegisterPage() {
  const { id = "" } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()

  const { data: event, isLoading: eventLoading, error: eventError } = useEvent(id)
  const { data: profile, isLoading: profileLoading } = useProfile()
  const { data: waiver } = useWaiver()
  const register = useRegister(id)

  const [accepted, setAccepted] = useState(false)
  const [guardian, setGuardian] = useState(false)
  const [minutes, setMinutes] = useState("")

  if (eventLoading || profileLoading) return <Skeleton className="m-4 mx-auto h-96 max-w-2xl" />

  if (eventError || !event)
    return (
      <main className="mx-auto max-w-2xl p-4">
        <Alert variant="destructive"><AlertTitle>Event not found</AlertTitle></Alert>
      </main>
    )

  const distance = event.distances.find((d) => d.id === params.get("distance"))
  const back = <Link to={`/events/${event.id}`} className="text-sm text-muted-foreground hover:underline">← {event.name}</Link>

  if (!profile)
    return (
      <main className="mx-auto max-w-2xl space-y-4 p-4 sm:p-6">
        {back}
        <Alert>
          <AlertTitle>One quick thing first</AlertTitle>
          <AlertDescription>
            We need your runner profile (date of birth, emergency contact) before you can register.{" "}
            <Link to="/account/profile" className="underline">Set up your profile →</Link>
          </AlertDescription>
        </Alert>
      </main>
    )

  if (!distance)
    return (
      <main className="mx-auto max-w-2xl space-y-4 p-4 sm:p-6">
        {back}
        <Alert variant="destructive">
          <AlertDescription>Please choose a distance from the event page.</AlertDescription>
        </Alert>
      </main>
    )

  const age = ageOn(profile.date_of_birth, event.event_date)
  const tooYoung = age < distance.min_age
  const minor = age < 18
  const canSubmit = !!waiver && accepted && (!minor || guardian) && !tooYoung

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!waiver || !distance) return
    register.mutate(
      {
        distance_id: distance.id,
        waiver_version: waiver.version,
        guardian_consent: guardian,
        estimated_finish_minutes: minutes ? Number(minutes) : null,
      },
      { onSuccess: (reg) => navigate(`/registrations/${reg.id}`, { replace: true }) },
    )
  }

  return (
    <main className="mx-auto max-w-2xl space-y-6 p-4 sm:p-6">
      {back}
      <h1 className="text-2xl font-bold sm:text-3xl">Register</h1>

      <Card>
        <CardHeader>
          <CardTitle>{event.name} · {distance.name}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          {formatDate(event.event_date)} · {event.location}
          <div className="mt-1 font-medium text-foreground">
            {distance.fee === "0.00" ? "Free entry" : `Entry fee ${formatKES(distance.fee)}`}
          </div>
        </CardContent>
      </Card>

      {tooYoung && (
        <Alert variant="destructive">
          <AlertDescription>
            You'll be {age} on race day, and the minimum age for the {distance.name} is {distance.min_age}.
          </AlertDescription>
        </Alert>
      )}

      <form onSubmit={onSubmit} className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="eta">Estimated finish time in minutes (optional)</Label>
          <Input id="eta" type="number" inputMode="numeric" min={15} max={600}
            placeholder="e.g. 55" value={minutes} onChange={(e) => setMinutes(e.target.value)} />
          <p className="text-xs text-muted-foreground">Helps us place you in the right start wave.</p>
        </div>

        <div className="space-y-2">
          <Label>Liability waiver</Label>
          <div className="max-h-56 overflow-y-auto whitespace-pre-line rounded-md border p-3 text-sm">
            {waiver?.text ?? "Loading…"}
          </div>
          <div className="flex items-start gap-2 pt-1">
            <Checkbox id="waiver" checked={accepted} onCheckedChange={(v) => setAccepted(v === true)} />
            <Label htmlFor="waiver" className="font-normal leading-snug">
              I have read and accept the waiver above.
            </Label>
          </div>
        </div>

        {minor && (
          <div className="flex items-start gap-2">
            <Checkbox id="guardian" checked={guardian} onCheckedChange={(v) => setGuardian(v === true)} />
            <Label htmlFor="guardian" className="font-normal leading-snug">
              I am this runner's parent or legal guardian and I consent to their participation.
            </Label>
          </div>
        )}

        {register.error && (
          <Alert variant="destructive">
            <AlertDescription>{register.error.message}</AlertDescription>
          </Alert>
        )}

        <Button type="submit" size="lg" className="w-full sm:w-auto" disabled={!canSubmit || register.isPending}>
          {register.isPending ? "Registering…" : "Complete registration"}
        </Button>
      </form>
    </main>
  )
}