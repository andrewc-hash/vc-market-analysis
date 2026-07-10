import ReportViewer from "@/components/ReportViewer";
import { reportGolden } from "@/fixtures/reportGolden";

// Static UI preview — renders the full report UI from a fixture, with NO pipeline
// run and NO API calls. Visit /preview after `npm run dev`.
export default function PreviewPage() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">UI Preview</h1>
        <p className="text-sm text-gray-500">
          Rendered from a static fixture — no pipeline, no API calls. Edit{" "}
          <code className="text-gray-400">src/fixtures/reportGolden.ts</code> to try different data
          (e.g. set <code className="text-gray-400">market_map</code> to null to see the fallback).
        </p>
      </div>
      <ReportViewer result={reportGolden} />
    </main>
  );
}
