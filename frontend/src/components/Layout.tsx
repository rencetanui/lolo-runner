import { Link, Outlet } from "react-router-dom"
import { useLogout, useMe } from "@/api/auth"
import { Button, buttonVariants } from "@/components/ui/button"
import { VerifyEmailBanner } from "@/pages/VerifyEmailBanner"

export default function Layout() {
  const { data: user } = useMe()
  const logout = useLogout()

  return (
    <>
      <header className="border-b bg-background">
        <VerifyEmailBanner />
        {/* FIX 1: Dropped the duplicate nested <Outlet /> that was forcing page code to bleed inside the header area */}
        <nav className="mx-auto flex max-w-5xl items-center justify-between p-4">
          <Link to="/" className="font-bold tracking-tight">Lolo Runner</Link>
          
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
      
      {/* FIX 2: Wrapped the authoritative page output mount path inside an isolated main container block layout */}
      <main className="mx-auto max-w-5xl">
        <Outlet />
      </main>
    </>
  )
}
