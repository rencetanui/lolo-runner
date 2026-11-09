import type { OrganizerEvent } from "@/api/organizer"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

export type EventDetails = {
  name: string
  event_date: string
  location: string
  registration_opens: string
  registration_closes: string
  refunds_until: string
  description: string
  venue_details: string
  map_url: string
  contact_email: string
  contact_phone: string
}

export const emptyDetails = (): EventDetails => ({
  name: "", event_date: "", location: "", registration_opens: "", registration_closes: "", refunds_until: "",
  description: "", venue_details: "", map_url: "", contact_email: "", contact_phone: "",
})

export const toDetails = (e: OrganizerEvent): EventDetails => ({
  name: e.name,
  event_date: e.event_date,
  location: e.location,
  registration_opens: e.registration_opens,
  registration_closes: e.registration_closes,
  refunds_until: e.refunds_until ?? "",
  description: e.description ?? "",
  venue_details: e.venue_details ?? "",
  map_url: e.map_url ?? "",
  contact_email: e.contact_email ?? "",
  contact_phone: e.contact_phone ?? "",
})

// The same shape works for creating and for editing: empty optional fields become null (cleared).
export const detailsPayload = (d: EventDetails) => ({
  name: d.name.trim(),
  event_date: d.event_date,
  location: d.location.trim(),
  registration_opens: d.registration_opens,
  registration_closes: d.registration_closes,
  refunds_until: d.refunds_until || null,
  description: d.description.trim() || null,
  venue_details: d.venue_details.trim() || null,
  map_url: d.map_url.trim() || null,
  contact_email: d.contact_email.trim() || null,
  contact_phone: d.contact_phone.trim() || null,
})

export function detailsError(d: EventDetails): string | null {
  if (d.name.trim().length < 3) return "Give the event a name (at least 3 characters)."
  if (d.location.trim().length < 2) return "Enter the location."
  if (!d.event_date || !d.registration_opens || !d.registration_closes)
    return "Fill in the event date and both registration dates."
  if (d.registration_opens > d.registration_closes) return "Registration can't close before it opens."
  if (d.registration_closes > d.event_date) return "Registration must close on or before the event date."
  if (d.refunds_until && d.refunds_until > d.event_date) return "Refunds must end on or before the event date."
  if (d.map_url.trim() && !/^https:\/\/\S+$/i.test(d.map_url.trim())) return "The map link must start with https://"
  if (d.description.length > 5000) return "The description is too long (5000 characters at most)."
  if (d.venue_details.length > 1000) return "The venue details are too long (1000 characters at most)."
  return null
}

export function EventDetailsFields({ value, onChange }: { value: EventDetails; onChange: (d: EventDetails) => void }) {
  const set = (key: keyof EventDetails) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
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

      <div className="space-y-2 sm:col-span-2">
        <Label htmlFor="ev-desc">About this race (optional)</Label>
        <Textarea id="ev-desc" rows={6} maxLength={5000} value={value.description} onChange={set("description")}
          placeholder="The route, what's included in the race pack, water points, prizes…" />
        <p className="text-xs text-muted-foreground">Plain text. Blank lines start a new paragraph.</p>
      </div>
      <div className="space-y-2 sm:col-span-2">
        <Label htmlFor="ev-venue">Getting there (optional)</Label>
        <Textarea id="ev-venue" rows={3} maxLength={1000} value={value.venue_details} onChange={set("venue_details")}
          placeholder="Meeting point, parking, transport…" />
      </div>
      <div className="space-y-2 sm:col-span-2">
        <Label htmlFor="ev-map">Map link (optional)</Label>
        <Input id="ev-map" type="url" placeholder="https://maps.app.goo.gl/…" value={value.map_url} onChange={set("map_url")} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="ev-email">Contact email (optional)</Label>
        <Input id="ev-email" type="email" value={value.contact_email} onChange={set("contact_email")} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="ev-phone">Contact phone (optional)</Label>
        <Input id="ev-phone" type="tel" value={value.contact_phone} onChange={set("contact_phone")} />
      </div>
      <p className="text-xs text-muted-foreground sm:col-span-2">
        Contact details are shown to everyone on the public event page.
      </p>
    </div>
  )
}