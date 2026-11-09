import { useMyRefund } from "@/api/refunds"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { formatDateTime, formatKES } from "@/lib/format"

export function RefundPanel({ registrationId }: { registrationId: string }) {
  const { data: refund } = useMyRefund(registrationId)
  if (!refund) return null

  if (refund.status === "paid")
    return (
      <Alert>
        <AlertTitle>Refund sent</AlertTitle>
        <AlertDescription>
          {formatKES(refund.amount)} was sent to {refund.phone}
          {refund.decided_at && ` on ${formatDateTime(refund.decided_at)}`}. M-Pesa reference:{" "}
          <strong>{refund.mpesa_reference}</strong>.
        </AlertDescription>
      </Alert>
    )
  if (refund.status === "rejected")
    return (
      <Alert variant="destructive">
        <AlertTitle>Refund not approved</AlertTitle>
        <AlertDescription>{refund.message}</AlertDescription>
      </Alert>
    )
  return (
    <Alert>
      <AlertTitle>Refund requested</AlertTitle>
      <AlertDescription>
        {formatKES(refund.amount)} will be sent to {refund.phone}. We'll email and text you when it's on its way.
      </AlertDescription>
    </Alert>
  )
}