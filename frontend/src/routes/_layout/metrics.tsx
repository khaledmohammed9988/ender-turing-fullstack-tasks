import { createFileRoute } from "@tanstack/react-router"
import { useQuery } from "@tanstack/react-query"
import { MetricsService } from "@/client"
import AccessDenied from "@/components/Common/AccessDenied"
import { requirePermission } from "@/lib/permissions"

export const Route = createFileRoute("/_layout/metrics")({
  beforeLoad: () => requirePermission("metrics:read"),
  errorComponent: AccessDenied,
  component: Metrics,
})

function Metrics() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["metrics"],
    queryFn: async () => (await MetricsService.readMetrics()).data,
  })
  if (isPending) return <p>Loading metrics…</p>
  if (isError)
    return <p role="alert">Could not load metrics. Please try again.</p>
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-bold">Metrics</h1>
      <p>Registered users: {data?.users}</p>
      <p>Items: {data?.items}</p>
    </section>
  )
}
