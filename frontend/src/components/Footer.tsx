import { Link } from "react-router-dom"

export function Footer() {
  return (
    <footer className="mt-12 border-t">
      <div className="mx-auto flex max-w-5xl flex-wrap gap-x-6 gap-y-2 p-6 text-sm text-muted-foreground">
        <Link to="/help" className="hover:underline">Help and contact</Link>
        <Link to="/terms" className="hover:underline">Terms</Link>
        <Link to="/privacy" className="hover:underline">Privacy</Link>
        <Link to="/refund-policy" className="hover:underline">Refunds</Link>
        <span>© {new Date().getFullYear()} Lolo Runner</span>
      </div>
    </footer>
  )
}