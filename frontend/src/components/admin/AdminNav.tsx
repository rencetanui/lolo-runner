import { Link, useLocation } from "react-router-dom"

export function AdminNav() {
  const { pathname } = useLocation()
  const item = (to: string, label: string) => (
    <Link
      to={to}
      className={`rounded-md px-3 py-1.5 text-sm ${pathname.startsWith(to) ? "bg-muted font-medium" : "text-muted-foreground hover:underline"}`}
    >
      {label}
    </Link>
  )
  return <nav className="flex gap-2">{item("/admin/payments", "Payments")}{item("/admin/refunds", "Refunds")}</nav>
}