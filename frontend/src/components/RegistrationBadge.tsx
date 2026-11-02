import { Badge } from "@/components/ui/badge"
import { registrationState } from "@/lib/format"

export function RegistrationBadge({ opens, closes }: { opens: string; closes: string }) {
  const state = registrationState(opens, closes)
  if (state === "open") return <Badge>Registration open</Badge>
  if (state === "soon") return <Badge variant="secondary">Opens soon</Badge>
  return <Badge variant="outline">Closed</Badge>
}