import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getShow,
  getEpisodes,
  generateShowEpisode,
  type Show,
  type Episode,
} from "../lib/api";
import { CHARACTER_LABELS, TIME_WINDOW_LABELS, SOURCE_TYPE_LABELS } from "../lib/constants";
import StatusBadge from "../components/StatusBadge";

export default function ShowDetail() {
  const { showId } = useParams<{ showId: string }>();
  const [show, setShow] = useState<Show | null>(null);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!showId) return;
    const id = Number(showId);
    Promise.all([getShow(id), getEpisodes(id)])
      .then(([s, eps]) => {
        setShow(s);
        setEpisodes(eps);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [showId]);

  const handleGenerate = async () => {
    if (!showId) return;
    setGenerating(true);
    try {
      await generateShowEpisode(Number(showId));
      // Refresh episodes list
      const eps = await getEpisodes(Number(showId));
      setEpisodes(eps);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
      </div>
    );
  }

  if (error || !show) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-neutral-950">
        <p className="text-sm text-neutral-400">{error || "Show not found"}</p>
        <Link to="/shows" className="text-sm text-amber-500 transition hover:text-amber-400">
          Back to shows
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-950">
      <div className="mx-auto max-w-2xl px-4 py-8">
        <Link
          to="/shows"
          className="inline-flex items-center gap-1.5 text-sm text-neutral-400 transition hover:text-neutral-200"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Shows
        </Link>

        <div className="mt-6 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-neutral-100">
              {show.name}
            </h1>
            <div className="mt-2 flex flex-wrap gap-2">
              <span className="inline-block rounded-full bg-neutral-800 px-2.5 py-0.5 text-xs text-neutral-400">
                {SOURCE_TYPE_LABELS[show.source_type] ?? show.source_type ?? "reMarkable"}
              </span>
              <span className="inline-block rounded-full bg-neutral-800 px-2.5 py-0.5 text-xs text-neutral-400">
                {CHARACTER_LABELS[show.character] ?? show.character}
              </span>
              <span className="inline-block rounded-full bg-neutral-800 px-2.5 py-0.5 text-xs text-neutral-400">
                {TIME_WINDOW_LABELS[show.time_window] ?? show.time_window}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            <Link
              to={`/shows/${show.id}/edit`}
              className="rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 transition hover:border-neutral-700 hover:text-neutral-300"
            >
              Edit
            </Link>
          </div>
        </div>

        {/* Generate button */}
        <div className="mt-8 flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Episodes
          </h2>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-neutral-950 transition hover:bg-amber-500 disabled:opacity-50"
          >
            {generating ? "Generating..." : "Generate Now"}
          </button>
        </div>

        {episodes.length === 0 && (
          <div className="mt-4 rounded-xl border border-neutral-900 bg-neutral-900/30 p-12 text-center">
            <p className="text-sm text-neutral-400">
              No episodes yet. Hit "Generate Now" to create the first one.
            </p>
          </div>
        )}

        {episodes.length > 0 && (
          <div className="mt-4 space-y-3">
            {episodes.map((ep) => (
              <Link
                key={ep.id}
                to={`/episode/${ep.id}`}
                className="block rounded-xl border border-neutral-900 bg-neutral-900/30 p-5 transition hover:border-neutral-800 hover:bg-neutral-900/60"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-xs text-neutral-500">{ep.date}</p>
                    <h3 className="mt-1 truncate text-sm font-medium text-neutral-200">
                      {ep.title || "Untitled Episode"}
                    </h3>
                  </div>
                  <StatusBadge status={ep.status} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
