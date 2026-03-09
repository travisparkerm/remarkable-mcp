import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getEpisode, getAudioUrl, type Episode } from "../lib/api";
import AudioPlayer from "../components/AudioPlayer";

export default function Player() {
  const { date } = useParams<{ date: string }>();
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!date) return;
    getEpisode(date)
      .then(setEpisode)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [date]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
      </div>
    );
  }

  if (error || !episode) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-neutral-950">
        <p className="text-sm text-neutral-400">
          {error || "Episode not found"}
        </p>
        <Link
          to="/"
          className="text-sm text-amber-500 transition hover:text-amber-400"
        >
          Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-950">
      <div className="mx-auto max-w-2xl px-4 py-8">
        {/* Back link */}
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-neutral-400 transition hover:text-neutral-200"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Back
        </Link>

        {/* Date heading */}
        <h1 className="mt-6 text-2xl font-semibold tracking-tight text-neutral-100">
          {date}
        </h1>
        {episode.title && (
          <p className="mt-1 text-sm text-neutral-400">{episode.title}</p>
        )}

        {/* Audio player */}
        <div className="mt-6">
          {episode.status === "ready" ? (
            <AudioPlayer src={getAudioUrl(date!)} />
          ) : (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5 text-center text-sm text-neutral-400">
              Audio is not available yet. Status: {episode.status}
            </div>
          )}
        </div>

        {/* Transcript */}
        {episode.script_text && (
          <div className="mt-8">
            <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-neutral-500">
              Transcript
            </h2>
            <div className="rounded-xl border border-neutral-900 bg-neutral-900/30 p-6">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-neutral-300">
                {episode.script_text}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
