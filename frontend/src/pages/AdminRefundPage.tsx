import { useState } from "react"
import { Link, useParams } from "react-router-dom"
import { useAdminRefund, useMarkRefundPaid, useRejectRefund, type AdminRefundDetail } from "@/api/admin"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { formatDate, formatDateTime, formatKES } from "@/lib/format"
import { REASON_LABEL, RefundStatusBadge } from "./AdminRefundsPage"

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  )
}

function Actions({ refund }: { refund: AdminRefundDetail }) {
  const paid = useMarkRefundPaid(refund.id)
  const reject = useRejectRefund(refund.id)
  const [reference, setReference] = useState("")
  const [note, setNote] = useState("")
  const [reason, setReason] = useState("")

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>I've sent the money</CardTitle>
          <CardDescription>
            Send {formatKES(refund.amount)} to <strong>{refund.phone}</strong> from your M-Pesa business account,
            then enter the transaction code from the confirmation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              if (window.confirm(`Record ${formatKES(refund.amount)} as sent to ${refund.phone}? The runner will be told.`))
                paid.mutate({ mpesa_reference: reference.trim(), note: note.trim() || null })
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="ref">M-Pesa transaction code</Label>
              <Input id="ref" required minLength={6} maxLength={20} value={reference} onChange={(e) => setReference(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="paid-note">Note (optional, internal)</Label>
              <Input id="paid-note" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
            {paid.error && <Alert variant="destructive"><AlertDescription>{paid.error.message}</AlertDescription></Alert>}
            <Button type="submit" disabled={paid.isPending}>{paid.isPending ? "Saving…" : "Mark as sent"}</Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Reject</CardTitle>
          <CardDescription>The runner sees this reason. Use it when the money isn't owed.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              if (window.confirm("Reject this refund? The runner will be told why.")) reject.mutate(reason.trim())
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="reject-reason">Reason</Label>
              <Textarea id="reject-reason" rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
            </div>
            {reject.error && <Alert variant="destructive"><AlertDescription>{reject.error.message}</AlertDescription></Alert>}
            <Button type="submit" variant="outline" disabled={reason.trim().length < 10 || reject.isPending}>
              {reject.isPending ? "Saving…" : "Reject refund"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

export default function AdminRefundPage() {
  const { id = "" } = useParams()
  const { data: r, isLoading, error } = useAdminRefund(id)

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <Link to="/admin/refunds" className="text-sm text-muted-foreground hover:underline">← All refunds</Link>
      {isLoading && <Skeleton className="h-64" />}
      {error && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}

      {r && (
        <>
          <header className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold">{formatKES(r.amount)}</h1>
            <RefundStatusBadge status={r.status} />
            <span className="text-sm text-muted-foreground">{REASON_LABEL[r.reason]}</span>
          </header>

          <Card>
            <CardContent className="pt-6">
              <dl className="grid gap-4 sm:grid-cols-2">
                <Row label="Send to">{r.phone}</Row>
                <Row label="Runner">{r.user.full_name} · {r.user.email}</Row>
                <Row label="Event">{r.event.name} · {formatDate(r.event.event_date)}</Row>
                <Row label="Distance and bib">{r.distance_name} · bib {r.bib_number}</Row>
                <Row label="Original payment">
                  <Link to={`/admin/payments/${r.payment_id}`} className="underline">{r.payment_receipt ?? "view payment"}</Link>
                </Row>
                <Row label="Requested">{formatDateTime(r.created_at)}</Row>
                {r.decided_at && <Row label="Decided">{formatDateTime(r.decided_at)} · {r.decided_by_name ?? "system"}</Row>}
                {r.mpesa_reference && <Row label="Refund transaction code">{r.mpesa_reference}</Row>}
                {r.admin_note && <Row label="Note">{r.admin_note}</Row>}
              </dl>
            </CardContent>
          </Card>

          {r.status === "requested" && <Actions refund={r} />}

          <section className="space-y-2">
            <h2 className="text-lg font-semibold">History</h2>
            <ul className="space-y-2 text-sm">
              {r.audit.map((a, i) => (
                <li key={i} className="rounded-md border p-3">
                  <div className="font-medium">
                    {a.action}{" "}
                    <span className="font-normal text-muted-foreground">· {a.actor_name ?? "system"} · {formatDateTime(a.created_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </main>
  )
}