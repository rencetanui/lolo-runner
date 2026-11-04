import { useEffect, useRef, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useVerifyEmail } from "@/api/auth"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { buttonVariants } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [token] = useState(() => params.get("token") ?? "")
  const verify = useVerifyEmail()
  const { mutate } = verify
  const started = useRef(false)

  useEffect(() => {
    if (!token || started.current) return
    started.current = true
    mutate(token)
    navigate("/verify-email", { replace: true })
  }, [token, mutate, navigate])

  return (
    <main className="mx-auto max-w-md space-y-4 p-4 sm:p-6">
      {verify.isPending && <Skeleton className="h-24" />}
      {verify.isSuccess && (
        <>
          <Alert>
            <AlertTitle>Email verified</AlertTitle>
            <AlertDescription>Thanks. You can now register for races.</AlertDescription>
          </Alert>
          <Link to="/" className={buttonVariants()}>Browse races</Link>
        </>
      )}
      {(verify.isError || !token) && !verify.isSuccess && !verify.isPending && (
        <Alert variant="destructive">
          <AlertTitle>That link didn't work</AlertTitle>
          <AlertDescription>
            {verify.error?.message ?? "This link is incomplete."} Log in and use the banner at the top
            of the page to get a new one.
          </AlertDescription>
        </Alert>
      )}
    </main>
  )
}