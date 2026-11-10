import { Link, Outlet } from "react-router-dom"
import { useLogout, useMe } from "@/api/auth"
import { Button, buttonVariants } from "@/components/ui/button"
import { VerifyEmailBanner } from "@/pages/VerifyEmailBanner"
import { useAdminSummary } from "@/api/admin"
import { Footer } from "./Footer"
import { TermsBanner } from "./TermsBanner"

export default function Layout() {
  const { data: user } = useMe()
  const logout = useLogout()
  const { data: attention } = useAdminSummary(user?.role === "admin")
  const alerts = attention
    ? attention.needs_review + attention.needs_refund + attention.stuck_pending + attention.refunds_requested + attention.support_open
    : 0

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b bg-background">
        <nav className="mx-auto flex max-w-5xl items-center justify-between p-4">
          <Link to="/" className="flex items-center">
            <img src="/logo.png" alt="Lolo Runner" className="h-10 w-auto" />
          </Link>
          {user ? (
            <div className="flex items-center gap-3">
              {(user.role === "organizer" || user.role === "admin") && (
                <>
                  <Link to="/organizer/events" className={buttonVariants({ variant: "ghost", size: "sm" })}>
                    Organizer dashboard
                  </Link>
                  <span className="text-sm text-muted-foreground">·</span>
                </>
              )}
              {user.role === "admin" && (
                <Link to="/admin/payments" className="text-sm hover:underline">
                  Admin
                  {alerts > 0 && (
                    <span className="ml-1 rounded-full bg-destructive px-1.5 py-0.5 text-xs text-white">{alerts}</span>
                  )}
                </Link>
              )}
              <Link to="/account" className="text-sm hover:underline">{user.full_name}</Link>
              <Button variant="outline" size="sm" onClick={() => logout.mutate()}>
                Log out
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link to="/login" className={buttonVariants({ variant: "ghost", size: "sm" })}>Log in</Link>
              <Link to="/signup" className={buttonVariants({ size: "sm" })}>Sign up</Link>
            </div>
          )}
        </nav>
      </header>

      <VerifyEmailBanner />
      <TermsBanner />

      <main className="mx-auto w-full max-w-5xl flex-1 p-4">
        <Outlet />
      </main>

      <Footer />
    </div>
  )
}
