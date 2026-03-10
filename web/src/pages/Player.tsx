import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { getEpisode, getAudioUrl, deleteEpisode, type Episode } from "../lib/api";
import AudioPlayer from "../components/AudioPlayer";

const POLL_INTERVAL = 3000;

const TERMINAL_STATUSES = new Set(["ready", "failed"]);

const STATUS_CONFIG: Record<
  string,
  { label: string; color: string; icon: string; step?: number }
> = {
  pending: {
    label: "Queued — waiting to start",
    color: "text-neutral-400",
    icon: "clock",
    step: 0,
  },
  extracting: {
    label: "Reading your reMarkable notes...",
    color: "text-amber-400",
    icon: "spinner",
    step: 1,
  },
  summarizing: {
    label: "Writing your podcast script...",
    color: "text-amber-400",
    icon: "spinner",
    step: 2,
  },
  generating_audio: {
    label: "Generating audio...",
    color: "text-amber-400",
    icon: "spinner",
    step: 3,
  },
  processing: {
    label: "Generating your episode...",
    color: "text-amber-400",
    icon: "spinner",
    step: 1,
  },
  ready: {
    label: "Ready",
    color: "text-emerald-400",
    icon: "check",
    step: 4,
  },
  failed: {
    label: "Generation failed",
    color: "text-red-400",
    icon: "x",
  },
};

const PIPELINE_STEPS = [
  { key: "extracting", label: "Extract" },
  { key: "summarizing", label: "Script" },
  { key: "generating_audio", label: "Audio" },
];

function StatusIndicator({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  const currentStep = config.step ?? 0;
  const isInProgress = !TERMINAL_STATUSES.has(status) && status !== "pending";

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
      {/* Progress steps */}
      {isInProgress && (
        <div className="mb-4 flex items-center gap-2">
          {PIPELINE_STEPS.map((step, i) => {
            const stepNum = i + 1;
            const done = currentStep > stepNum;
            const active = currentStep === stepNum;
            return (
              <div key={step.key} className="flex items-center gap-2 flex-1">
                <div className="flex items-center gap-2 flex-1">
                  <div
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium ${
                      done
                        ? "bg-emerald-900/50 text-emerald-400"
                        : active
                          ? "bg-amber-900/50 text-amber-400"
                          : "bg-neutral-800 text-neutral-500"
                    }`}
                  >
                    {done ? "\u2713" : stepNum}
                  </div>
                  <span
                    className={`text-xs ${
                      done
                        ? "text-emerald-400"
                        : active
                          ? "text-amber-400"
                          : "text-neutral-500"
                    }`}
                  >
                    {step.label}
                  </span>
                </div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <div
                    className={`h-px flex-1 ${
                      done ? "bg-emerald-800" : "bg-neutral-800"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Current status label */}
      <div className="flex items-center gap-3">
        {config.icon === "spinner" ? (
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
        ) : config.icon === "check" ? (
          <svg
            className="h-5 w-5 text-emerald-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        ) : config.icon === "x" ? (
          <svg
            className="h-5 w-5 text-red-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        ) : (
          <div className="h-2 w-2 rounded-full bg-neutral-600" />
        )}
        <span className={`text-sm font-medium ${config.color}`}>
          {config.label}
        </span>
      </div>
    </div>
  );
}

export default function Player() {
  const { episodeId } = useParams<{ episodeId: string }>();
  const navigate = useNavigate();
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const id = episodeId ? Number(episodeId) : null;

  const fetchEpisode = useCallback(() => {
    if (id === null) return;
    getEpisode(id)
      .then((ep) => {
        setEpisode(ep);
        if (TERMINAL_STATUSES.has(ep.status) && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      })
      .catch((err) => setError(err.message));
  }, [id]);

  useEffect(() => {
    if (id === null) return;
    getEpisode(id)
      .then((ep) => {
        setEpisode(ep);
        if (!TERMINAL_STATUSES.has(ep.status)) {
          intervalRef.current = setInterval(fetchEpisode, POLL_INTERVAL);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [id, fetchEpisode]);

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

  const isError =
    episode.status === "failed" ||
    (episode.script_text && episode.script_text.startsWith("Error:"));

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

        {/* Date heading + delete */}
        <div className="mt-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-neutral-100">
              {episode.title || episode.date}
            </h1>
            <p className="mt-1 text-sm text-neutral-500">{episode.date}</p>
          </div>
          <button
            onClick={async () => {
              if (id === null || deleting) return;
              if (!confirm("Delete this episode? You can regenerate it afterwards.")) return;
              setDeleting(true);
              try {
                await deleteEpisode(id);
                navigate("/");
              } catch (err: unknown) {
                setError(err instanceof Error ? err.message : "Delete failed");
                setDeleting(false);
              }
            }}
            disabled={deleting}
            className="rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 transition hover:border-red-900 hover:text-red-400 disabled:opacity-50"
          >
            {deleting ? "Deleting..." : "Delete"}
          </button>
        </div>

        {/* Status / Audio player */}
        <div className="mt-6">
          {episode.status === "ready" && id !== null ? (
            <AudioPlayer src={getAudioUrl(id)} />
          ) : (
            <StatusIndicator status={episode.status} />
          )}
        </div>

        {/* Error details */}
        {isError && episode.script_text && (
          <div className="mt-4 rounded-xl border border-red-900/50 bg-red-950/20 p-5">
            <p className="text-sm text-red-300 whitespace-pre-wrap">
              {episode.script_text.replace(/^Error:\s*/, "")}
            </p>
          </div>
        )}

        {/* Transcript — show as soon as available, even while audio generates */}
        {episode.script_text && !isError && (
          <div className="mt-8">
            <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-neutral-500">
              Transcript
              {episode.status === "generating_audio" && (
                <span className="ml-2 text-amber-500/70 normal-case tracking-normal">
                  — audio is still generating
                </span>
              )}
            </h2>
            <div className="rounded-xl border border-neutral-900 bg-neutral-900/30 p-6">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-neutral-300">
                {episode.script_text}
              </p>
            </div>
          </div>
        )}

        {/* Raw notes */}
        {episode.notes_text && (
          <div className="mt-8">
            <h2 className="mb-3 text-xs font-medium uppercase tracking-wider text-neutral-500">
              Raw Notes
            </h2>
            <div className="rounded-xl border border-neutral-900 bg-neutral-900/30 p-6">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-neutral-400">
                {episode.notes_text}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
