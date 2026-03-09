import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  getEpisodes,
  getRemarkableStatus,
  generateEpisode,
  type Episode,
  type User,
} from "../lib/api";

interface Props {
  user: User;
  onLogout: () => void;
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ready: "bg-emerald-900/50 text-emerald-400",
    generating: "bg-amber-900/50 text-amber-400",
    error: "bg-red-900/50 text-red-400",
    pending: "bg-neutral-800 text-neutral-400",
  };

  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status] ?? styles.pending}`}
    >
      {status}
    </span>
  );
}

export default function Dashboard({ user, onLogout }: Props) {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [remarkableConnected, setRemarkableConnected] = useState(true);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    Promise.all([getEpisodes(), getRemarkableStatus()])
      .then(([eps, status]) => {
        setEpisodes(eps);
        setRemarkableConnected(status.connected);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const today = new Date().toISOString().split("T")[0];
      await generateEpisode(today);
      const eps = await getEpisodes();
      setEpisodes(eps);
    } catch {
      // handle silently
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950">
      {/* Header */}
      <header className="border-b border-neutral-900">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-4">
          <h1 className="text-lg font-semibold tracking-tight text-neutral-100">
            reMarkable Podcast
          </h1>
          <div className="flex items-center gap-4">
            <Link
              to="/settings"
              className="text-sm text-neutral-400 transition hover:text-neutral-200"
            >
              Settings
            </Link>
            <div className="flex items-center gap-2">
              {user.picture && (
                <img
                  src={user.picture}
                  alt={user.name}
                  className="h-7 w-7 rounded-full"
                />
              )}
              <span className="hidden text-sm text-neutral-300 sm:inline">
                {user.name}
              </span>
            </div>
            <button
              onClick={onLogout}
              className="text-sm text-neutral-500 transition hover:text-neutral-300"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-8">
        {/* reMarkable not connected banner */}
        {!remarkableConnected && !loading && (
          <Link
            to="/settings"
            className="mb-8 block rounded-xl border border-amber-900/50 bg-amber-950/30 p-5 transition hover:border-amber-800/50"
          >
            <h3 className="text-sm font-medium text-amber-400">
              Connect your reMarkable
            </h3>
            <p className="mt-1 text-sm text-neutral-400">
              Link your tablet in Settings to start generating episodes from
              your notes.
            </p>
          </Link>
        )}

        {/* Generate button */}
        <div className="mb-8 flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Episodes
          </h2>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-neutral-950 transition hover:bg-amber-500 disabled:opacity-50"
          >
            {generating ? "Generating..." : "Generate Today's Episode"}
          </button>
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex justify-center py-20">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
          </div>
        )}

        {/* Empty state */}
        {!loading && episodes.length === 0 && (
          <div className="rounded-xl border border-neutral-900 bg-neutral-900/30 p-12 text-center">
            <p className="text-sm text-neutral-400">
              No episodes yet. Connect your reMarkable and generate your first
              episode.
            </p>
          </div>
        )}

        {/* Episode list */}
        {!loading && episodes.length > 0 && (
          <div className="space-y-3">
            {episodes.map((ep) => (
              <Link
                key={ep.date}
                to={`/episode/${ep.date}`}
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
      </main>
    </div>
  );
}
