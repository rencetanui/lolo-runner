import { useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { useLogin } from "@/api/auth"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { GoogleSignInButton } from "@/components/GoogleSignInButton"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const login = useLogin()
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/"

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    login.mutate({ email, password }, { onSuccess: () => navigate(from, { replace: true }) })
  }

  return (
    /* 
      FIX: Swapped generic padding elements for a robust layout structure:
      - 'min-h-[calc(100vh-4rem)]' offsets typical header spacing offsets.
      - 'flex items-center justify-center' anchors the login module directly in the viewport center.
    */
    <div className="flex min-h-[calc(100vh-6rem)] w-full items-center justify-center p-4 sm:p-6">
      <main className="w-full max-w-md">
        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle>Welcome back</CardTitle>
            <CardDescription>Log in to register for races.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="space-y-4">
              {login.error && (
                <Alert variant="destructive">
                  <AlertDescription>{login.error.message}</AlertDescription>
                </Alert>
              )}
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <div className="block pt-1">
                <Link to="/forgot-password" className="text-sm text-muted-foreground underline hover:text-foreground">
                  Forgot your password?
                </Link>
              </div>
              <Button type="submit" className="w-full" disabled={login.isPending}>
                {login.isPending ? "Logging in…" : "Log in"}
              </Button>
              <p className="text-center text-sm text-muted-foreground pt-2">
                No account? <Link to="/signup" className="underline hover:text-foreground">Sign up</Link>
              </p>
            </form>
            <div className="relative mt-6 mb-4">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">Or continue with</span>
              </div>
            </div>
            <div>
              <GoogleSignInButton onSignedIn={() => navigate(from, { replace: true })} />
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
