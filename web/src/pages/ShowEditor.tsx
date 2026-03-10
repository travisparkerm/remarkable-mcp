import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  createShow,
  getShow,
  updateShow,
  getPersonalities,
  getRemarkableLibrary,
  type Personality,
  type RemarkableItem,
  type ShowCreate,
} from "../lib/api";

const TIME_WINDOWS = [
  { value: "1d", label: "Last day", desc: "Notes modified in the last 24 hours" },
  { value: "7d", label: "Last week", desc: "Notes modified in the last 7 days" },
  { value: "30d", label: "Last month", desc: "Notes modified in the last 30 days" },
  { value: "all", label: "All time", desc: "All notes in scope, no time filter" },
];

const CADENCES = [
  { value: "on-demand", label: "On-demand", desc: "Generate manually" },
  { value: "daily", label: "Daily", desc: "Generate every day" },
  { value: "weekly", label: "Weekly", desc: "Generate once per week" },
  { value: "monthly", label: "Monthly", desc: "Generate once per month" },
];

export default function ShowEditor() {
  const { showId } = useParams<{ showId: string }>();
  const isEditing = showId !== undefined && showId !== "new";
  const navigate = useNavigate();

  const [form, setForm] = useState<ShowCreate>({
    name: "",
    scope: "/",
    time_window: "7d",
    character: "analyst",
    cadence: "on-demand",
    schedule: null,
    voice_id: null,
    target_word_count: 350,
  });
  const [personalities, setPersonalities] = useState<Personality[]>([]);
  const [libraryItems, setLibraryItems] = useState<RemarkableItem[]>([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [libraryError, setLibraryError] = useState("");
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(isEditing);

  useEffect(() => {
    getPersonalities().then(setPersonalities).catch(() => {});

    if (isEditing) {
      getShow(Number(showId))
        .then((show) => {
          setForm({
            name: show.name,
            scope: show.scope,
            time_window: show.time_window,
            character: show.character,
            cadence: show.cadence,
            schedule: show.schedule,
            voice_id: show.voice_id,
            target_word_count: show.target_word_count,
          });
          // Parse existing scope into selected paths
          try {
            const paths = JSON.parse(show.scope);
            if (Array.isArray(paths)) setSelectedPaths(paths);
            else setSelectedPaths([show.scope]);
          } catch {
            setSelectedPaths(show.scope === "/" ? [] : [show.scope]);
          }
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [showId, isEditing]);

  const handleBrowseLibrary = async () => {
    setLibraryOpen(true);
    if (libraryItems.length > 0) return;
    setLibraryLoading(true);
    setLibraryError("");
    try {
      const items = await getRemarkableLibrary();
      setLibraryItems(items);
    } catch (err) {
      setLibraryError(err instanceof Error ? err.message : "Failed to load library");
    } finally {
      setLibraryLoading(false);
    }
  };

  const togglePath = (path: string) => {
    setSelectedPaths((prev) => {
      const next = prev.includes(path)
        ? prev.filter((p) => p !== path)
        : [...prev, path];
      const scope = next.length === 0 ? "/" : JSON.stringify(next);
      setForm((f) => ({ ...f, scope }));
      return next;
    });
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      setError("Show name is required");
      return;
    }
    setSaving(true);
    setError("");
    try {
      if (isEditing) {
        await updateShow(Number(showId), form);
      } else {
        await createShow(form);
      }
      navigate("/shows");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
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

        <h1 className="mt-6 text-2xl font-semibold tracking-tight text-neutral-100">
          {isEditing ? "Edit Show" : "New Show"}
        </h1>

        {error && (
          <div className="mt-4 rounded-lg border border-red-900/50 bg-red-950/20 p-3">
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {/* Name */}
        <section className="mt-8">
          <label className="block text-sm font-medium text-neutral-400">
            Show Name
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="e.g., Work Week in Review"
            className="mt-2 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-amber-600"
          />
        </section>

        {/* Scope */}
        <section className="mt-8">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Scope
          </h2>
          <p className="mt-1 text-xs text-neutral-600">
            Which notebooks or folders to include
          </p>
          <div className="mt-3 rounded-xl border border-neutral-900 bg-neutral-900/30 p-4">
            {selectedPaths.length === 0 ? (
              <p className="text-sm text-neutral-500">
                All notebooks (entire library)
              </p>
            ) : (
              <div className="space-y-1">
                {selectedPaths.map((p) => (
                  <div
                    key={p}
                    className="flex items-center justify-between rounded-lg bg-neutral-800/50 px-3 py-1.5"
                  >
                    <span className="text-sm text-neutral-300">{p}</span>
                    <button
                      onClick={() => togglePath(p)}
                      className="text-xs text-neutral-500 hover:text-red-400"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}
            <button
              onClick={handleBrowseLibrary}
              className="mt-3 rounded-lg border border-neutral-700 px-3 py-1.5 text-xs text-neutral-300 transition hover:border-amber-600 hover:text-amber-400"
            >
              Browse Library
            </button>
          </div>

          {/* Library browser modal */}
          {libraryOpen && (
            <div className="mt-3 max-h-72 overflow-y-auto rounded-xl border border-neutral-800 bg-neutral-900 p-3">
              {libraryLoading ? (
                <div className="flex flex-col items-center gap-3 py-8">
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
                  <p className="text-xs text-neutral-500">
                    Fetching your reMarkable library from the cloud...
                  </p>
                  <p className="text-xs text-neutral-600">
                    This can take up to a minute on first load
                  </p>
                </div>
              ) : (
                <>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-medium text-neutral-500">
                      Select folders or documents
                    </span>
                    <button
                      onClick={() => setLibraryOpen(false)}
                      className="text-xs text-neutral-500 hover:text-neutral-300"
                    >
                      Close
                    </button>
                  </div>
                  {libraryItems.map((item) => {
                    const isSelected = selectedPaths.includes(item.path);
                    const depth = (item.path.match(/\//g) || []).length - 1;
                    return (
                      <button
                        key={item.id}
                        onClick={() => togglePath(item.path)}
                        className={`flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left text-sm transition ${
                          isSelected
                            ? "bg-amber-950/30 text-amber-400"
                            : "text-neutral-300 hover:bg-neutral-800"
                        }`}
                        style={{ paddingLeft: `${12 + depth * 16}px` }}
                      >
                        {item.is_folder ? (
                          <svg className="h-4 w-4 shrink-0 text-neutral-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                          </svg>
                        ) : (
                          <svg className="h-4 w-4 shrink-0 text-neutral-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        )}
                        <span className="truncate">{item.name}</span>
                        {isSelected && (
                          <svg className="ml-auto h-4 w-4 shrink-0 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </button>
                    );
                  })}
                  {libraryError && (
                    <p className="py-4 text-center text-xs text-red-400">
                      {libraryError}
                    </p>
                  )}
                  {!libraryError && libraryItems.length === 0 && (
                    <p className="py-4 text-center text-xs text-neutral-500">
                      No items found. Make sure your reMarkable is connected.
                    </p>
                  )}
                </>
              )}
            </div>
          )}
        </section>

        {/* Time Window */}
        <section className="mt-8">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Time Window
          </h2>
          <p className="mt-1 text-xs text-neutral-600">
            How far back to look for notes
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {TIME_WINDOWS.map((tw) => {
              const selected = form.time_window === tw.value;
              return (
                <button
                  key={tw.value}
                  onClick={() => setForm({ ...form, time_window: tw.value })}
                  className={`rounded-xl border p-3 text-left transition ${
                    selected
                      ? "border-amber-600 bg-amber-950/30"
                      : "border-neutral-900 bg-neutral-900/30 hover:border-neutral-800"
                  }`}
                >
                  <span
                    className={`text-sm font-medium ${selected ? "text-amber-400" : "text-neutral-200"}`}
                  >
                    {tw.label}
                  </span>
                  <p className="mt-0.5 text-xs text-neutral-500">{tw.desc}</p>
                </button>
              );
            })}
          </div>
        </section>

        {/* Character */}
        <section className="mt-8">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Character
          </h2>
          <p className="mt-1 text-xs text-neutral-600">
            The editorial lens for this show
          </p>
          <div className="mt-3 grid gap-2">
            {personalities.map((p) => {
              const selected = form.character === p.key;
              return (
                <button
                  key={p.key}
                  onClick={() => setForm({ ...form, character: p.key })}
                  className={`rounded-xl border p-4 text-left transition ${
                    selected
                      ? "border-amber-600 bg-amber-950/30"
                      : "border-neutral-900 bg-neutral-900/30 hover:border-neutral-800"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={`h-2 w-2 rounded-full ${selected ? "bg-amber-500" : "bg-neutral-700"}`}
                    />
                    <span
                      className={`text-sm font-medium ${selected ? "text-amber-400" : "text-neutral-200"}`}
                    >
                      {p.name}
                    </span>
                    <span className="text-xs text-neutral-500">— {p.tagline}</span>
                  </div>
                  <p className="mt-1.5 pl-4 text-xs text-neutral-500">
                    {p.description}
                  </p>
                </button>
              );
            })}
          </div>
        </section>

        {/* Cadence */}
        <section className="mt-8">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Cadence
          </h2>
          <p className="mt-1 text-xs text-neutral-600">
            How often to generate episodes
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {CADENCES.map((c) => {
              const selected = form.cadence === c.value;
              return (
                <button
                  key={c.value}
                  onClick={() => setForm({ ...form, cadence: c.value })}
                  className={`rounded-xl border p-3 text-left transition ${
                    selected
                      ? "border-amber-600 bg-amber-950/30"
                      : "border-neutral-900 bg-neutral-900/30 hover:border-neutral-800"
                  }`}
                >
                  <span
                    className={`text-sm font-medium ${selected ? "text-amber-400" : "text-neutral-200"}`}
                  >
                    {c.label}
                  </span>
                  <p className="mt-0.5 text-xs text-neutral-500">{c.desc}</p>
                </button>
              );
            })}
          </div>
        </section>

        {/* Voice & Length */}
        <section className="mt-8">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Voice & Length
          </h2>
          <div className="mt-3 space-y-4 rounded-xl border border-neutral-900 bg-neutral-900/30 p-5">
            <div>
              <label className="block text-sm text-neutral-400">
                ElevenLabs Voice ID
              </label>
              <input
                type="text"
                value={form.voice_id ?? ""}
                onChange={(e) =>
                  setForm({ ...form, voice_id: e.target.value || null })
                }
                placeholder="Leave blank to use character default"
                className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-amber-600"
              />
            </div>
            <div>
              <label className="block text-sm text-neutral-400">
                Target word count
              </label>
              <input
                type="number"
                value={form.target_word_count ?? 350}
                onChange={(e) =>
                  setForm({
                    ...form,
                    target_word_count: e.target.value
                      ? parseInt(e.target.value)
                      : 350,
                  })
                }
                className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-amber-600"
              />
            </div>
          </div>
        </section>

        {/* Save */}
        <div className="mt-8 flex items-center gap-3 pb-12">
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-amber-600 px-6 py-2.5 text-sm font-medium text-neutral-950 transition hover:bg-amber-500 disabled:opacity-50"
          >
            {saving
              ? "Saving..."
              : isEditing
                ? "Save Changes"
                : "Create Show"}
          </button>
          <Link
            to="/shows"
            className="rounded-lg border border-neutral-800 px-4 py-2 text-sm text-neutral-400 transition hover:border-neutral-700 hover:text-neutral-300"
          >
            Cancel
          </Link>
        </div>
      </div>
    </div>
  );
}
