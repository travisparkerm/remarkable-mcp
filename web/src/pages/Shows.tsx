import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  getShows,
  deleteShow,
  type Show,
  type User,
} from "../lib/api";

const CHARACTER_LABELS: Record<string, string> = {
  logbook: "The Logbook",
  analyst: "The Analyst",
  coach: "The Coach",
  connector: "The Connector",
  creative: "The Creative",
  editor: "The Editor",
};

const TIME_WINDOW_LABELS: Record<string, string> = {
  "1d": "Last day",
  "7d": "Last week",
  "30d": "Last month",
  all: "All time",
};

const CADENCE_LABELS: Record<string, string> = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  "on-demand": "On-demand",
};

interface Props {
  user: User;
}

export default function Shows({ user: _user }: Props) {
  const [shows, setShows] = useState<Show[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    getShows()
      .then(setShows)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (showId: number, name: string) => {
    if (!confirm(`Delete "${name}" and all its episodes?`)) return;
    try {
      await deleteShow(showId);
      setShows((prev) => prev.filter((s) => s.id !== showId));
    } catch {}
  };

  return (
    <div className="min-h-screen bg-neutral-950">
      <div className="mx-auto max-w-2xl px-4 py-8">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-neutral-400 transition hover:text-neutral-200"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </Link>

        <div className="mt-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight text-neutral-100">
            Shows
          </h1>
          <button
            onClick={() => navigate("/shows/new")}
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-neutral-950 transition hover:bg-amber-500"
          >
            New Show
          </button>
        </div>

        {loading && (
          <div className="flex justify-center py-20">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
          </div>
        )}

        {!loading && shows.length === 0 && (
          <div className="mt-8 rounded-xl border border-neutral-900 bg-neutral-900/30 p-12 text-center">
            <p className="text-sm text-neutral-400">
              No shows yet. Create your first show to start generating episodes
              from your reMarkable notes.
            </p>
          </div>
        )}

        {!loading && shows.length > 0 && (
          <div className="mt-6 space-y-3">
            {shows.map((show) => (
              <div
                key={show.id}
                className="rounded-xl border border-neutral-900 bg-neutral-900/30 p-5 transition hover:border-neutral-800"
              >
                <div className="flex items-start justify-between gap-4">
                  <Link to={`/shows/${show.id}`} className="min-w-0 flex-1">
                    <h3 className="text-sm font-medium text-neutral-200">
                      {show.name}
                    </h3>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <span className="inline-block rounded-full bg-neutral-800 px-2.5 py-0.5 text-xs text-neutral-400">
                        {CHARACTER_LABELS[show.character] ?? show.character}
                      </span>
                      <span className="inline-block rounded-full bg-neutral-800 px-2.5 py-0.5 text-xs text-neutral-400">
                        {TIME_WINDOW_LABELS[show.time_window] ?? show.time_window}
                      </span>
                      <span className="inline-block rounded-full bg-neutral-800 px-2.5 py-0.5 text-xs text-neutral-400">
                        {CADENCE_LABELS[show.cadence] ?? show.cadence}
                      </span>
                    </div>
                    {show.last_run_at && (
                      <p className="mt-2 text-xs text-neutral-600">
                        Last run: {new Date(show.last_run_at).toLocaleDateString()}
                      </p>
                    )}
                  </Link>
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/shows/${show.id}/edit`}
                      className="rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 transition hover:border-neutral-700 hover:text-neutral-300"
                    >
                      Edit
                    </Link>
                    <button
                      onClick={() => handleDelete(show.id, show.name)}
                      className="rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 transition hover:border-red-900 hover:text-red-400"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
