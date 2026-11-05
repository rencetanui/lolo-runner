import { useState } from "react"
import { Link } from "react-router-dom"
import { useChangePassword, useMe } from "@/api/auth"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function ChangePasswordPage() {

  const { data: user } = useMe()

  const [current, setCurrent] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [localError, setLocalError] = useState<string | null>(null)
  const change = useChangePassword()

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (password !== confirm) return setLocalError("The two new passwords don't match.")
    setLocalError(null)
    change.mutate(
      { current_password: current, new_password: password },
      { onSuccess: () => { setCurrent(""); setPassword(""); setConfirm("") } },
    )
  }

    if (user && !user.has_password) {
    return (
      <main className="mx-auto max-w-md space-y-4 p-4 sm:p-6">
        <Link to="/account" className="text-sm text-muted-foreground hover:underline">← My account</Link>
        <Alert>
          <AlertDescription>
            You signed up with Google, so you don't have a password yet. If you'd like one,{" "}
            <Link to="/forgot-password" className="underline">we'll email you a link to set it</Link>.
          </AlertDescription>
        </Alert>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-md space-y-4 p-4 sm:p-6">
      <Link to="/account" className="text-sm text-muted-foreground hover:underline">← My account</Link>
      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
          <CardDescription>Every other device you're signed in on will be signed out.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            {(localError || change.error) && (
              <Alert variant="destructive"><AlertDescription>{localError ?? change.error?.message}</AlertDescription></Alert>
            )}
            {change.isSuccess && <Alert><AlertDescription>{change.data.message}</AlertDescription></Alert>}
            <div className="space-y-2">
              <Label htmlFor="current">Current password</Label>
              <Input id="current" type="password" autoComplete="current-password" required
                value={current} onChange={(e) => setCurrent(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new">New password</Label>
              <Input id="new" type="password" autoComplete="new-password" required minLength={8}
                value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm">Confirm new password</Label>
              <Input id="confirm" type="password" autoComplete="new-password" required minLength={8}
                value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </div>
            <Button type="submit" disabled={change.isPending}>
              {change.isPending ? "Saving…" : "Change password"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}