import { useEffect, useRef, useState } from "react"
import { useGoogleConfig, useGoogleLogin } from "@/api/auth"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { loadGoogleIdentity } from "@/lib/googleIdentity"
import { Link } from "react-router-dom"

export function GoogleSignInButton({ onSignedIn }: { onSignedIn: () => void }) {
  const { data: config } = useGoogleConfig()
  const login = useGoogleLogin()
  const holder = useRef<HTMLDivElement>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  // Google's callback is registered once, so it reads the latest handlers through a ref.
  const latest = useRef({ mutate: login.mutate, onSignedIn })
  useEffect(() => {
    latest.current = { mutate: login.mutate, onSignedIn }
  })

  const enabled = config?.enabled ?? false
  const clientId = config?.client_id ?? null

  useEffect(() => {
    const el = holder.current
    if (!enabled || !clientId || !el) return
    let cancelled = false
    loadGoogleIdentity()
      .then(() => {
        if (cancelled || !window.google) return
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (response) =>
            latest.current.mutate(response.credential, { onSuccess: () => latest.current.onSignedIn() }),
        })
        window.google.accounts.id.renderButton(el, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "continue_with",
          shape: "rectangular",
          width: Math.min(400, Math.max(200, el.clientWidth)),
        })
      })
      .catch((e: Error) => {
        if (!cancelled) setLoadError(e.message)
      })
    return () => {
      cancelled = true
      el.innerHTML = ""
    }
  }, [enabled, clientId])

  if (!enabled) return null

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <div className="h-px flex-1 bg-border" />
        or
        <div className="h-px flex-1 bg-border" />
      </div>
      <div ref={holder} className="flex min-h-[44px] justify-center" />
        <p className="text-center text-xs text-muted-foreground">
          By continuing with Google you agree to the <Link to="/terms" className="underline">Terms</Link> and{" "}
          <Link to="/privacy" className="underline">Privacy Notice</Link>.
        </p>
      {login.isPending && <p className="text-center text-sm text-muted-foreground">Signing you in…</p>}
      {(login.error || loadError) && (
        <Alert variant="destructive">
          <AlertDescription>{login.error?.message ?? loadError}</AlertDescription>
        </Alert>
      )}
    </div>
  )
}