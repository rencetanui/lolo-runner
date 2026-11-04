import { useState } from "react"
import { Link } from "react-router-dom"
import { useForgotPassword } from "@/api/auth"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const forgot = useForgotPassword()

  return (
    <main className="mx-auto max-w-md p-4 sm:p-6">
      <Card>
        <CardHeader>
          <CardTitle>Forgot your password?</CardTitle>
          <CardDescription>Enter your email and we'll send you a link to choose a new one.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {forgot.isSuccess ? (
            <Alert><AlertDescription>{forgot.data.message}</AlertDescription></Alert>
          ) : (
            <form
              className="space-y-4"
              onSubmit={(e) => {
                e.preventDefault()
                forgot.mutate(email.trim())
              }}
            >
              {forgot.error && (
                <Alert variant="destructive"><AlertDescription>{forgot.error.message}</AlertDescription></Alert>
              )}
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" autoComplete="email" required
                  value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
              <Button type="submit" className="w-full" disabled={forgot.isPending}>
                {forgot.isPending ? "Sending…" : "Send reset link"}
              </Button>
            </form>
          )}
          <p className="text-center text-sm text-muted-foreground">
            <Link to="/login" className="underline">Back to log in</Link>
          </p>
        </CardContent>
      </Card>
    </main>
  )
}