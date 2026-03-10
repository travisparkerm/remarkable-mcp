import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  getEpisodes,
  getShows,
  getRemarkableStatus,
  type Episode,
  type Show,
  type User,
} from "../lib/api";

interface Props {
  user: User;
  onLogout: () => void;
}

const CHARACTER_LABELS: Record<string, string> = {
  logbook: "The Logbook",
  analyst: "The Analyst",
  coach: "The Coach",
  connector: "The Connector",
  creative: "The Creative",
  editor: "The Editor",
};

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ready: "bg-emerald-900/50 text-emerald-400",
    generating: "bg-amber-900/50 text-amber-400",
    processing: "bg-amber-900/50 text-amber-400",
    error: "bg-red-900/50 text-red-400",
    failed: "bg-red-900/50 text-red-400",
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
  const [shows, setShows] = useState<Show[]>([]);
  const [remarkableConnected, setRemarkableConnected] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getEpisodes(), getShows(), getRemarkableStatus()])
      .then(([eps, s, status]) => {
        setEpisodes(eps);
        setShows(s);
        setRemarkableConnected(status.connected);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Build a map of show_id -> show name for display
  const showNames = new Map<number, string>();
  for (const s of shows) {
    showNames.set(s.id, s.name);
  }

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
              to="/shows"
              className="text-sm text-neutral-400 transition hover:text-neutral-200"
            >
              Shows
            </Link>
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

        {/* Shows summary */}
        {!loading && shows.length === 0 && remarkableConnected && (
          <Link
            to="/shows/new"
            className="mb-8 block rounded-xl border border-amber-900/50 bg-amber-950/30 p-5 transition hover:border-amber-800/50"
          >
            <h3 className="text-sm font-medium text-amber-400">
              Create your first show
            </h3>
            <p className="mt-1 text-sm text-neutral-400">
              Set up a show to start generating podcast episodes from your
              reMarkable notes.
            </p>
          </Link>
        )}

        {!loading && shows.length > 0 && (
          <section className="mb-8">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
                Your Shows
              </h2>
              <Link
                to="/shows"
                className="text-xs text-neutral-500 transition hover:text-neutral-300"
              >
                Manage
              </Link>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {shows.slice(0, 4).map((show) => (
                <Link
                  key={show.id}
                  to={`/shows/${show.id}`}
                  className="rounded-xl border border-neutral-900 bg-neutral-900/30 p-4 transition hover:border-neutral-800 hover:bg-neutral-900/60"
                >
                  <h3 className="text-sm font-medium text-neutral-200">
                    {show.name}
                  </h3>
                  <p className="mt-1 text-xs text-neutral-500">
                    {CHARACTER_LABELS[show.character] ?? show.character}
                  </p>
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* Recent episodes */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Recent Episodes
          </h2>
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
              No episodes yet. Create a show and generate your first episode.
            </p>
          </div>
        )}

        {/* Episode list */}
        {!loading && episodes.length > 0 && (
          <div className="space-y-3">
            {episodes.map((ep) => (
              <Link
                key={ep.id}
                to={`/episode/${ep.id}`}
                className="block rounded-xl border border-neutral-900 bg-neutral-900/30 p-5 transition hover:border-neutral-800 hover:bg-neutral-900/60"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="text-xs text-neutral-500">
                      {ep.date}
                      {ep.show_id && showNames.has(ep.show_id) && (
                        <span className="ml-2 text-neutral-600">
                          {showNames.get(ep.show_id)}
                        </span>
                      )}
                    </p>
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
