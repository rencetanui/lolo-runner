import { Link, Outlet } from "react-router-dom"
import { useLogout, useMe } from "@/api/auth"
import { Button } from "@/components/ui/button"

export default function Layout() {
  const { data: user } = useMe()
  const logout = useLogout()

  return (
    <>
      <header className="border-b">
        <nav className="mx-auto flex max-w-5xl items-center justify-between p-4">
          <Link to="/" className="font-bold">Lolo Runner</Link>
          {user ? (
            <div className="flex items-center gap-3">
              <Link to="/account" className="text-sm hover:underline">{user.full_name}</Link>
              <Button variant="outline" size="sm" onClick={() => logout.mutate()}>
                Log out
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" asChild><Link to="/login">Log in</Link></Button>
              <Button size="sm" asChild><Link to="/signup">Sign up</Link></Button>
            </div>
          )}
        </nav>
      </header>
      <Outlet />
    </>
  )
}