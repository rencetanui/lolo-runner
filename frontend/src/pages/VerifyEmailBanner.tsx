import { useMe, useResendVerification } from "@/api/auth"
import { Button } from "@/components/ui/button"

export function VerifyEmailBanner() {
  const { data: user } = useMe()
  const resend = useResendVerification()
  if (!user || user.email_verified) return null

  return (
    <div className="border-b bg-muted">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 p-3 text-sm">
        <span>
          {resend.isSuccess
            ? resend.data.message
            : resend.error
              ? resend.error.message
              : <>Please verify <strong>{user.email}</strong> to register for races. Check your inbox for the link.</>}
        </span>
        {!resend.isSuccess && (
          <Button size="sm" variant="outline" onClick={() => resend.mutate()} disabled={resend.isPending}>
            {resend.isPending ? "Sending…" : "Resend email"}
          </Button>
        )}
      </div>
    </div>
  )
}