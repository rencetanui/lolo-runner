import { useState } from "react"
import { Link, useParams } from "react-router-dom"
import {
  useAdminPayment, useRecheckPayment, useResolvePayment, type AdminPaymentDetail,
} from "@/api/admin"
import { PaymentStatusBadge } from "@/components/admin/PaymentStatusBadge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { formatDate, formatDateTime, formatKES } from "@/lib/format"

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  )
}

function ResolveForm({ payment }: { payment: AdminPaymentDetail }) {
  const resolve = useResolvePayment(payment.id)
  const [action, setAction] = useState<"confirm" | "dismiss">("confirm")
  const [note, setNote] = useState("")
  const [receipt, setReceipt] = useState("")
  const [localError, setLocalError] = useState<string | null>(null)

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (note.trim().length < 10) return setLocalError("Explain your decision in at least 10 characters. It's kept in the audit log.")
    setLocalError(null)
    const verb = action === "confirm" ? "CONFIRM this payment and the registration" : "DISMISS this payment"
    if (window.confirm(`Are you sure you want to ${verb}?`)) {
      resolve.mutate({ action, note: note.trim(), mpesa_receipt: receipt.trim() || null })
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Decide</CardTitle>
        <CardDescription>
          Check the M-Pesa statement first. Confirm only if the right amount really arrived for this runner.
          Dismiss only if no money moved. If money arrived but you can't honour it, leave it here until the
          refund tools arrive.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="flex gap-6 text-sm">
            <label className="flex items-center gap-2">
              <input type="radio" checked={action === "confirm"} onChange={() => setAction("confirm")} /> Confirm payment
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" checked={action === "dismiss"} onChange={() => setAction("dismiss")} /> Dismiss (no money moved)
            </label>
          </div>
          {action === "confirm" && (
            <div className="space-y-2">
              <Label htmlFor="receipt">M-Pesa reference from the statement (optional)</Label>
              <Input id="receipt" maxLength={30} value={receipt} onChange={(e) => setReceipt(e.target.value)} />
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="note">Why?</Label>
            <Textarea id="note" rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          {(localError || resolve.error) && (
            <Alert variant="destructive"><AlertDescription>{localError ?? resolve.error?.message}</AlertDescription></Alert>
          )}
          <Button type="submit" disabled={resolve.isPending}>{resolve.isPending ? "Saving…" : "Save decision"}</Button>
        </form>
      </CardContent>
    </Card>
  )
}

export default function AdminPaymentPage() {
  const { id = "" } = useParams()
  const { data: p, isLoading, error } = useAdminPayment(id)
  const recheck = useRecheckPayment(id)

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <Link to="/admin/payments" className="text-sm text-muted-foreground hover:underline">← All payments</Link>
      {isLoading && <Skeleton className="h-64" />}
      {error && <Alert variant="destructive"><AlertDescription>{error.message}</AlertDescription></Alert>}

      {p && (
        <>
          <header className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold">{formatKES(p.amount)}</h1>
            <PaymentStatusBadge status={p.status} />
            {p.needs_refund && <span className="text-sm text-destructive">Needs a refund</span>}
          </header>

          {p.status === "needs_review" && (
            <Alert variant="destructive">
              <AlertTitle>Needs review</AlertTitle>
              <AlertDescription>{p.result_desc}</AlertDescription>
            </Alert>
          )}

          <Card>
            <CardContent className="pt-6">
              <dl className="grid gap-4 sm:grid-cols-2">
                <Row label="Runner">{p.user.full_name} · {p.user.email}</Row>
                <Row label="Paid from">{p.phone}</Row>
                <Row label="Event">{p.event.name} · {formatDate(p.event.event_date)}</Row>
                <Row label="Distance and bib">{p.distance_name} · bib {p.bib_number}</Row>
                <Row label="Registration">{p.registration_status}</Row>
                <Row label="M-Pesa reference">{p.mpesa_receipt ?? "—"}</Row>
                <Row label="Started">{formatDateTime(p.created_at)}</Row>
                <Row label="Finished">{p.completed_at ? formatDateTime(p.completed_at) : "—"}</Row>
                <Row label="M-Pesa result">{p.result_code ?? "—"} {p.result_desc && `· ${p.result_desc}`}</Row>
                {p.admin_note && <Row label="Admin note">{p.admin_note}</Row>}
              </dl>
            </CardContent>
          </Card>

          {p.status === "pending" && (
            <div className="space-y-2">
              <Button variant="outline" onClick={() => recheck.mutate()} disabled={recheck.isPending}>
                {recheck.isPending ? "Asking M-Pesa…" : "Ask M-Pesa for the result"}
              </Button>
              {recheck.error && <Alert variant="destructive"><AlertDescription>{recheck.error.message}</AlertDescription></Alert>}
            </div>
          )}

          {p.status === "needs_review" && <ResolveForm payment={p} />}

          <section className="space-y-2">
            <h2 className="text-lg font-semibold">History</h2>
            {p.audit.length === 0 && <p className="text-sm text-muted-foreground">No admin or system actions recorded.</p>}
            <ul className="space-y-2 text-sm">
              {p.audit.map((a, i) => (
                <li key={i} className="rounded-md border p-3">
                  <div className="font-medium">{a.action} <span className="font-normal text-muted-foreground">· {a.actor_name ?? "system"} · {formatDateTime(a.created_at)}</span></div>
                  {a.detail && <div className="text-muted-foreground">{String(a.detail.note ?? a.detail.reason ?? "")}</div>}
                </li>
              ))}
            </ul>
          </section>

          <details className="text-sm">
            <summary className="cursor-pointer text-muted-foreground">Raw M-Pesa data</summary>
            <pre className="mt-2 overflow-auto rounded-md border bg-muted/40 p-3 text-xs">
              {JSON.stringify(p.raw_callback, null, 2) ?? "none"}
            </pre>
          </details>
        </>
      )}
    </main>
  )
}