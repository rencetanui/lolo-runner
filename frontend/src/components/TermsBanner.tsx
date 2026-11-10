import { Link } from "react-router-dom"
import { useAcceptTerms, useMe } from "@/api/auth"
import { Button } from "@/components/ui/button"

export function TermsBanner() {
  const { data: user } = useMe()
  const accept = useAcceptTerms()
  if (!user || !user.needs_terms) return null
  return (
    <div className="border-b bg-muted">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 p-3 text-sm">
        <span>
          Please read our <Link to="/terms" className="underline">Terms</Link> and{" "}
          <Link to="/privacy" className="underline">Privacy Notice</Link>. You need to accept them to register for races.
          {accept.error && <span className="ml-2 text-destructive">{accept.error.message}</span>}
        </span>
        <Button size="sm" onClick={() => accept.mutate()} disabled={accept.isPending}>
          {accept.isPending ? "Saving…" : "I accept"}
        </Button>
      </div>
    </div>
  )
}