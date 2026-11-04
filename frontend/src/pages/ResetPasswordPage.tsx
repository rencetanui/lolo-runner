import { useEffect, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useResetPassword } from "@/api/auth"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [token] = useState(() => params.get("token") ?? "")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [localError, setLocalError] = useState<string | null>(null)
  const reset = useResetPassword()

  // Keep the secret out of the address bar and the browser history.
  useEffect(() => {
    if (token) navigate("/reset-password", { replace: true })
  }, [token, navigate])

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (password !== confirm) return setLocalError("The two passwords don't match.")
    setLocalError(null)
    reset.mutate({ token, new_password: password })
  }

  return (
    <main className="mx-auto max-w-md p-4 sm:p-6">
      <Card>
        <CardHeader>
          <CardTitle>Choose a new password</CardTitle>
          <CardDescription>At least 8 characters. You'll be signed out on all devices.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!token && !reset.isSuccess ? (
            <Alert variant="destructive">
              <AlertDescription>
                This link is incomplete. <Link to="/forgot-password" className="underline">Request a new one</Link>.
              </AlertDescription>
            </Alert>
          ) : reset.isSuccess ? (
            <>
              <Alert><AlertDescription>{reset.data.message}</AlertDescription></Alert>
              <Link to="/login" className={buttonVariants({ className: "w-full" })}>Log in</Link>
            </>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4">
              {(localError || reset.error) && (
                <Alert variant="destructive">
                  <AlertDescription>
                    {localError ?? reset.error?.message}{" "}
                    {reset.error && <Link to="/forgot-password" className="underline">Request a new link</Link>}
                  </AlertDescription>
                </Alert>
              )}
              <div className="space-y-2">
                <Label htmlFor="new-password">New password</Label>
                <Input id="new-password" type="password" autoComplete="new-password" required minLength={8}
                  value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm-password">Confirm new password</Label>
                <Input id="confirm-password" type="password" autoComplete="new-password" required minLength={8}
                  value={confirm} onChange={(e) => setConfirm(e.target.value)} />
              </div>
              <Button type="submit" className="w-full" disabled={reset.isPending}>
                {reset.isPending ? "Saving…" : "Change password"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </main>
  )
}