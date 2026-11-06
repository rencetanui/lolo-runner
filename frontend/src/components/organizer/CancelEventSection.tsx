import { useState } from "react"
import { useCancelEvent, useCancelPreview, type OrganizerEvent } from "@/api/organizer"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { formatKES } from "@/lib/format"

export function CancelEventSection({ event }: { event: OrganizerEvent }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const preview = useCancelPreview(event.id, open)
  const cancel = useCancelEvent(event.id)

  function onCancel(e: React.FormEvent) {
    e.preventDefault()
    if (window.confirm("Cancel this event for everyone? This can't be undone.")) cancel.mutate(reason.trim())
  }

  return (
    <section className="space-y-3 border-t pt-6">
      <h2 className="text-lg font-semibold">Cancel event</h2>
      <p className="text-sm text-muted-foreground">
        If the event can't go ahead, cancel it. Everyone who registered is told by email and SMS, and every
        paid entry is queued for a full refund.
      </p>
      {!open ? (
        <Button variant="outline" onClick={() => setOpen(true)}>Cancel this event…</Button>
      ) : (
        <form onSubmit={onCancel} className="space-y-4 rounded-md border p-4">
          {preview.data && (
            <Alert>
              <AlertDescription>
                {preview.data.registrations} registration(s) will be cancelled.{" "}
                {preview.data.paid_registrations > 0
                  ? `${preview.data.paid_registrations} paid, so ${formatKES(preview.data.refund_total)} will be queued for refund.`
                  : "None has paid, so no refunds are needed."}
              </AlertDescription>
            </Alert>
          )}
          <div className="space-y-2">
            <Label htmlFor="cancel-reason">Reason (shown to everyone who registered)</Label>
            <Textarea id="cancel-reason" rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          {cancel.error && <Alert variant="destructive"><AlertDescription>{cancel.error.message}</AlertDescription></Alert>}
          <div className="flex gap-2">
            <Button type="submit" variant="destructive" disabled={reason.trim().length < 10 || cancel.isPending}>
              {cancel.isPending ? "Cancelling…" : "Cancel event and notify everyone"}
            </Button>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Keep the event</Button>
          </div>
        </form>
      )}
    </section>
  )
}