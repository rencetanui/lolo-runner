import { useEffect, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useConfirmDeletion } from "@/api/account"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button, buttonVariants } from "@/components/ui/button"

export default function ConfirmDeletePage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [token] = useState(() => params.get("token") ?? "")
  const confirm = useConfirmDeletion()

  // Keep the secret out of the address bar and the browser history.
  useEffect(() => {
    if (token) navigate("/confirm-delete", { replace: true })
  }, [token, navigate])

  if (confirm.isSuccess)
    return (
      <main className="mx-auto max-w-md space-y-4 p-4 sm:p-6">
        <Alert>
          <AlertTitle>Your account has been deleted</AlertTitle>
          <AlertDescription>
            We've removed your profile and personal details, and emailed you a confirmation. Goodbye, and thanks for running with us.
          </AlertDescription>
        </Alert>
        <Link to="/" className={buttonVariants()}>Back to the home page</Link>
      </main>
    )

  return (
    <main className="mx-auto max-w-md space-y-4 p-4 sm:p-6">
      <h1 className="text-2xl font-bold">Delete your account</h1>
      {!token ? (
        <Alert variant="destructive">
          <AlertDescription>
            This link is incomplete. <Link to="/account" className="underline">Go to your account</Link> to start again.
          </AlertDescription>
        </Alert>
      ) : (
        <>
          <Alert variant="destructive">
            <AlertTitle>This can't be undone</AlertTitle>
            <AlertDescription>
              Your profile, contact details and messages will be permanently deleted. Payment and registration records
              are kept for our financial records, without your personal details. You'll be signed out everywhere.
            </AlertDescription>
          </Alert>
          {confirm.error && (
            <Alert variant="destructive">
              <AlertDescription>
                {confirm.error.message} <Link to="/account" className="underline">Back to your account</Link>
              </AlertDescription>
            </Alert>
          )}
          <div className="flex gap-2">
            <Button variant="destructive" disabled={confirm.isPending} onClick={() => confirm.mutate(token)}>
              {confirm.isPending ? "Deleting…" : "Permanently delete my account"}
            </Button>
            <Link to="/account" className={buttonVariants({ variant: "outline" })}>Keep my account</Link>
          </div>
        </>
      )}
    </main>
  )
}