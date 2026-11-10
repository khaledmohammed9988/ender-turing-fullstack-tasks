import { Link } from "@tanstack/react-router"
import ErrorComponent from "./ErrorComponent"
import { AccessDeniedError } from "@/lib/permissions"

export default function AccessDenied({ error }: { error: unknown }) {
  if (!(error instanceof AccessDeniedError)) return <ErrorComponent />
  return (
    <section role="alert" className="space-y-4 p-8">
      <h1 className="text-2xl font-bold">Access denied</h1>
      <p>Your account does not have permission to view this page.</p>
      <Link to="/" className="underline">
        Return to dashboard
      </Link>
    </section>
  )
}
