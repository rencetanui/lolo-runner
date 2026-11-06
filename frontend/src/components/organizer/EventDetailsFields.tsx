import type { OrganizerEvent } from "@/api/organizer"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export type EventDetails = {
  name: string
  event_date: string
  location: string
  registration_opens: string
  registration_closes: string
  refunds_until: string
}

export const emptyDetails = (): EventDetails => ({
  name: "", event_date: "", location: "", registration_opens: "", registration_closes: "", refunds_until: "",
})

export const toDetails = (e: OrganizerEvent): EventDetails => ({
  name: e.name,
  event_date: e.event_date,
  location: e.location,
  registration_opens: e.registration_opens,
  registration_closes: e.registration_closes,
  refunds_until: e.refunds_until ?? "",
})

export function detailsError(d: EventDetails): string | null {
  if (d.name.trim().length < 3) return "Give the event a name (at least 3 characters)."
  if (d.location.trim().length < 2) return "Enter the location."
  if (!d.event_date || !d.registration_opens || !d.registration_closes)
    return "Fill in the event date and both registration dates."
  if (d.registration_opens > d.registration_closes) return "Registration can't close before it opens."
  if (d.registration_closes > d.event_date) return "Registration must close on or before the event date."
  if (d.refunds_until && d.refunds_until > d.event_date) return "Refunds must end on or before the event date."
  return null
}

export function EventDetailsFields({ value, onChange }: { value: EventDetails; onChange: (d: EventDetails) => void }) {
  const set = (key: keyof EventDetails) => (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange({ ...value, [key]: e.target.value })

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="space-y-2 sm:col-span-2">
        <Label htmlFor="ev-name">Event name</Label>
        <Input id="ev-name" value={value.name} onChange={set("name")} maxLength={150} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="ev-date">Event date</Label>
        <Input id="ev-date" type="date" value={value.event_date} onChange={set("event_date")} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="ev-loc">Location</Label>
        <Input id="ev-loc" value={value.location} onChange={set("location")} maxLength={150} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="ev-opens">Registration opens</Label>
        <Input id="ev-opens" type="date" value={value.registration_opens} onChange={set("registration_opens")} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="ev-closes">Registration closes</Label>
        <Input id="ev-closes" type="date" value={value.registration_closes} onChange={set("registration_closes")} />
      </div>
        <div className="space-y-2 sm:col-span-2">
        <Label htmlFor="ev-refunds">Refunds available until (optional)</Label>
        <Input id="ev-refunds" type="date" value={value.refunds_until} onChange={set("refunds_until")} />
        <p className="text-xs text-muted-foreground">
          Runners who cancel on or before this date get a full refund. Leave it empty for non-refundable entries.
          If you cancel the event itself, everyone who paid is refunded regardless.
        </p>
      </div>
    </div>
  )
}