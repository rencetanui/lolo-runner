import type { PaymentStatus } from "@/api/admin"
import { Badge } from "@/components/ui/badge"

const LABEL: Record<PaymentStatus, string> = {
  pending: "Pending",
  succeeded: "Paid",
  failed: "Failed",
  needs_review: "Needs review",
}

export function PaymentStatusBadge({ status }: { status: PaymentStatus }) {
  const variant = status === "succeeded" ? "default" : status === "needs_review" ? "destructive" : "secondary"
  return <Badge variant={variant}>{LABEL[status]}</Badge>
}