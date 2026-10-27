import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { components } from "../api/schema";
import { formatCoordinates } from "../components/SitePicker";
import { CoverChart } from "../components/CoverChart";
import { CoverStrip } from "../components/CoverStrip";
import { Badge } from "../components/arc/badge/badge";
import { MetricCard } from "../components/arc/metric-card/metric-card";
import { SortableDataTable, type DataColumn } from "../components/arc/sortable-data-table/sortable-data-table";
import { Button } from "../components/arc/button/button";

type SiteDetail = components["schemas"]["SiteDetail"];
type Survey = components["schemas"]["Survey"];

export const Route = createFileRoute("/sites/$id")({
  component: SiteRoute,
});

function SiteRoute() {
  const { id } = Route.useParams();

  const siteQuery = useQuery({
    queryKey: ["site", id],
    queryFn: async (): Promise<SiteDetail | null> => {
      const { data } = await api.GET("/api/sites/{site_id}", {
        params: { path: { site_id: id } },
      });
      return data ?? null;
    },
  });

  const siteDetail = siteQuery.data;
  const site = siteDetail?.site;
  const surveys = siteDetail?.surveys ?? [];

  // Sort chronological ascending to find first and latest surveys
  const sortedSurveys = [...surveys].sort((a, b) =>
    a.dive_date.localeCompare(b.dive_date)
  );

  const firstSurvey = sortedSurveys[0];
  const latestSurvey = sortedSurveys[sortedSurveys.length - 1];

  const firstLive = firstSurvey?.cover?.live_coral ?? 0;
  const latestLive = latestSurvey?.cover?.live_coral ?? 0;
  const changePp = Math.round((latestLive - firstLive) * 1000) / 10;
  const changeText =
    changePp >= 0 ? `+${changePp.toFixed(1)} pp` : `−${Math.abs(changePp).toFixed(1)} pp`;

  const columns: DataColumn<Survey & Record<string, unknown>>[] = [
    {
      key: "dive_date",
      label: "Date",
      sortable: true,
      render: (_, row) => (
        <span className="font-mono text-label text-fg tabular-nums">
          {row.dive_date}
        </span>
      ),
    },
    {
      key: "live_cover",
      label: "Live cover",
      sortable: true,
      numeric: true,
      render: (_, row) => (
        <span className="font-mono text-label font-semibold text-fg tabular-nums">
          {row.cover ? `${Math.round(row.cover.live_coral * 100)}%` : "—"}
        </span>
      ),
    },
    {
      key: "cover",
      label: "Cover composition",
      render: (_, row) =>
        row.cover ? (
          <div className="w-36 sm:w-48 py-1">
            <CoverStrip cover={row.cover} />
          </div>
        ) : null,
    },
    {
      key: "verdict",
      label: "Verdict",
      render: (_, row) => {
        const live = row.cover?.live_coral ?? 0;
        const tone = live >= 0.4 ? "success" : live >= 0.25 ? "warning" : "danger";
        const label = live >= 0.4 ? "Healthy" : live >= 0.25 ? "Declining" : "Bleached";
        return <Badge tone={tone} size="sm">{label}</Badge>;
      },
    },
    {
      key: "actions",
      label: "",
      render: (_, row) => (
        <Link
          to="/surveys/$id"
          params={{ id: row.id }}
          className="inline-flex items-center gap-1 font-mono text-label text-accent hover:underline whitespace-nowrap"
        >
          Case file →
        </Link>
      ),
    },
  ];

  return (
    <div className="min-h-[calc(100vh-48px-32px)] bg-bg p-4 sm:p-6 lg:p-8 space-y-8 text-fg max-w-full overflow-x-hidden">
      {/* Header */}
      <header className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-display font-semibold tracking-tight text-fg">
              {site?.name ?? id}
            </h1>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              {site?.location ? (
                <p className="font-mono text-label text-secondary tabular-nums">
                  {formatCoordinates(site.location)}
                </p>
              ) : null}
              <span className="font-mono text-label text-muted">
                {id}
              </span>
            </div>
          </div>

          {site?.mpa_id ? (
            <Badge tone="info" size="md">
              MPA Protected
            </Badge>
          ) : null}
        </div>
      </header>

      {/* Figures row: 4 metric-cards */}
      {surveys.length > 0 ? (
        <section
          aria-label="Site key figures"
          className="grid grid-cols-2 lg:grid-cols-4 gap-4"
        >
          <MetricCard
            label="Live cover now"
            value={Math.round(latestLive * 100)}
            suffix="%"
            context={latestSurvey ? `Latest dive: ${latestSurvey.dive_date}` : "No dives"}
          />
          <MetricCard
            label="Change"
            value={Math.abs(changePp)}
            suffix=" pp"
            change={changeText}
            context="Since first survey"
          />
          <MetricCard
            label="Surveys"
            value={surveys.length}
            context="Recorded dives"
          />
          <MetricCard
            label="Latest heat stress"
            value={1}
            context="Alert Level 1"
          />
        </section>
      ) : null}

      {/* Empty State */}
      {surveys.length === 0 ? (
        <section
          aria-label="No surveys recorded"
          className="rounded-lg border border-hairline bg-surface p-12 text-center space-y-4"
        >
          <p className="text-body text-secondary max-w-md mx-auto">
            No surveys at this site yet. Upload a dive to start its record.
          </p>
          <div>
            <Link to="/upload">
              <Button variant="primary">Upload a dive</Button>
            </Link>
          </div>
        </section>
      ) : (
        <>
          {/* 01 COVER OVER TIME */}
          <section aria-labelledby="cover-heading" className="space-y-4">
            <h2
              id="cover-heading"
              className="font-mono text-label uppercase tracking-wider text-muted"
            >
              01&nbsp;&nbsp;COVER OVER TIME
            </h2>
            <CoverChart surveys={surveys} />
          </section>

          {/* 02 SURVEYS */}
          <section aria-labelledby="surveys-heading" className="space-y-4">
            <h2
              id="surveys-heading"
              className="font-mono text-label uppercase tracking-wider text-muted"
            >
              02&nbsp;&nbsp;SURVEYS
            </h2>
            <div className="rounded-lg border border-hairline bg-surface overflow-x-auto max-w-full">
              <SortableDataTable
                rows={sortedSurveys.slice().reverse() as (Survey & Record<string, unknown>)[]}
                columns={columns}
                rowKey="id"
                caption="Recorded site surveys"
              />
            </div>
          </section>
        </>
      )}
    </div>
  );
}
