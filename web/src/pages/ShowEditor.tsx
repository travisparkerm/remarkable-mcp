import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  createShow,
  getShow,
  updateShow,
  getPersonalities,
  getRemarkableLibrary,
  getAlbums,
  getPhotos,
  getPhotoThumbnailUrl,
  type Album,
  type Personality,
  type PhotoRecord,
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

const SOURCE_TYPES = [
  {
    value: "remarkable",
    label: "reMarkable",
    desc: "Pull notes from your reMarkable tablet",
    icon: (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
      </svg>
    ),
  },
  {
    value: "photo_library",
    label: "Photo Library",
    desc: "Upload photos of journal pages",
    icon: (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    ),
  },
];

export default function ShowEditor() {
  const { showId } = useParams<{ showId: string }>();
  const isEditing = showId !== undefined && showId !== "new";
  const navigate = useNavigate();

  const [form, setForm] = useState<ShowCreate>({
    name: "",
    source_type: "remarkable",
    source_config: null,
    scope: "/",
    time_window: "7d",
    character: "analyst",
    cadence: "on-demand",
    schedule: null,
    voice_id: null,
    target_word_count: 350,
  });
  const [personalities, setPersonalities] = useState<Personality[]>([]);

  // reMarkable source state
  const [libraryItems, setLibraryItems] = useState<RemarkableItem[]>([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [libraryError, setLibraryError] = useState("");
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);

  // Photo library source state
  const [albums, setAlbums] = useState<Album[]>([]);
  const [selectedAlbumId, setSelectedAlbumId] = useState<number | null>(null);
  const [selectedPhotoIds, setSelectedPhotoIds] = useState<number[]>([]);
  const [photoSourceMode, setPhotoSourceMode] = useState<"album" | "photos">("album");
  const [albumPhotos, setAlbumPhotos] = useState<PhotoRecord[]>([]);
  const [allPhotos, setAllPhotos] = useState<PhotoRecord[]>([]);
  const [photosLoading, setPhotosLoading] = useState(false);

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
            source_type: show.source_type || "remarkable",
            source_config: show.source_config,
            scope: show.scope,
            time_window: show.time_window,
            character: show.character,
            cadence: show.cadence,
            schedule: show.schedule,
            voice_id: show.voice_id,
            target_word_count: show.target_word_count,
          });

          // Parse reMarkable scope
          if (show.source_type === "remarkable" || !show.source_type) {
            try {
              const paths = JSON.parse(show.scope);
              if (Array.isArray(paths)) setSelectedPaths(paths);
              else setSelectedPaths([show.scope]);
            } catch {
              setSelectedPaths(show.scope === "/" ? [] : [show.scope]);
            }
          }

          // Parse photo library source config
          if (show.source_type === "photo_library" && show.source_config) {
            try {
              const config = JSON.parse(show.source_config);
              if (config.album_id) {
                setPhotoSourceMode("album");
                setSelectedAlbumId(config.album_id);
              } else if (config.photo_ids) {
                setPhotoSourceMode("photos");
                setSelectedPhotoIds(config.photo_ids);
              }
            } catch {}
          }
        })
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [showId, isEditing]);

  // Load albums when photo_library is selected
  useEffect(() => {
    if (form.source_type === "photo_library") {
      setPhotosLoading(true);
      Promise.all([getAlbums(), getPhotos()])
        .then(([a, p]) => {
          setAlbums(a);
          setAllPhotos(p);
        })
        .catch(() => {})
        .finally(() => setPhotosLoading(false));
    }
  }, [form.source_type]);

  // Load album photos when album is selected
  useEffect(() => {
    if (selectedAlbumId && photoSourceMode === "album") {
      getPhotos(selectedAlbumId).then(setAlbumPhotos).catch(() => {});
    }
  }, [selectedAlbumId, photoSourceMode]);

  // Update source_config when photo selections change
  useEffect(() => {
    if (form.source_type !== "photo_library") return;

    let config: string | null = null;
    if (photoSourceMode === "album" && selectedAlbumId) {
      config = JSON.stringify({ album_id: selectedAlbumId });
    } else if (photoSourceMode === "photos" && selectedPhotoIds.length > 0) {
      config = JSON.stringify({ photo_ids: selectedPhotoIds });
    }
    setForm((f) => ({ ...f, source_config: config }));
  }, [photoSourceMode, selectedAlbumId, selectedPhotoIds, form.source_type]);

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

  const togglePhotoId = (id: number) => {
    setSelectedPhotoIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      setError("Show name is required");
      return;
    }
    if (form.source_type === "photo_library" && !form.source_config) {
      setError("Please select an album or photos for this show");
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

        {/* Source Type */}
        <section className="mt-8">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Input Source
          </h2>
          <p className="mt-1 text-xs text-neutral-600">
            Where to pull notes from
          </p>
          <div className="mt-3 grid grid-cols-2 gap-3">
            {SOURCE_TYPES.map((st) => {
              const selected = form.source_type === st.value;
              return (
                <button
                  key={st.value}
                  onClick={() => setForm({ ...form, source_type: st.value, source_config: null })}
                  className={`flex items-start gap-3 rounded-xl border p-4 text-left transition ${
                    selected
                      ? "border-amber-600 bg-amber-950/30"
                      : "border-neutral-900 bg-neutral-900/30 hover:border-neutral-800"
                  }`}
                >
                  <div className={selected ? "text-amber-400" : "text-neutral-500"}>
                    {st.icon}
                  </div>
                  <div>
                    <span
                      className={`text-sm font-medium ${selected ? "text-amber-400" : "text-neutral-200"}`}
                    >
                      {st.label}
                    </span>
                    <p className="mt-0.5 text-xs text-neutral-500">{st.desc}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        {/* Source Config: reMarkable */}
        {form.source_type === "remarkable" && (
          <>
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

            {/* Time Window (reMarkable) */}
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
          </>
        )}

        {/* Source Config: Photo Library */}
        {form.source_type === "photo_library" && (
          <section className="mt-8">
            <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
              Photo Source
            </h2>
            <p className="mt-1 text-xs text-neutral-600">
              Choose an album or pick specific photos
            </p>

            {photosLoading ? (
              <div className="mt-4 flex justify-center py-8">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
              </div>
            ) : (
              <>
                {/* Mode toggle */}
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => setPhotoSourceMode("album")}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                      photoSourceMode === "album"
                        ? "bg-amber-600 text-neutral-950"
                        : "bg-neutral-900 text-neutral-400 hover:text-neutral-200"
                    }`}
                  >
                    Select Album
                  </button>
                  <button
                    onClick={() => setPhotoSourceMode("photos")}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                      photoSourceMode === "photos"
                        ? "bg-amber-600 text-neutral-950"
                        : "bg-neutral-900 text-neutral-400 hover:text-neutral-200"
                    }`}
                  >
                    Pick Photos
                  </button>
                </div>

                {photoSourceMode === "album" ? (
                  <div className="mt-3 space-y-2">
                    {albums.length === 0 ? (
                      <div className="rounded-xl border border-neutral-900 bg-neutral-900/30 p-6 text-center">
                        <p className="text-sm text-neutral-500">No albums yet.</p>
                        <Link
                          to="/photos"
                          className="mt-2 inline-block text-xs text-amber-500 hover:text-amber-400"
                        >
                          Go to Photo Library to create one
                        </Link>
                      </div>
                    ) : (
                      albums.map((a) => {
                        const selected = selectedAlbumId === a.id;
                        return (
                          <button
                            key={a.id}
                            onClick={() => setSelectedAlbumId(a.id)}
                            className={`flex w-full items-center justify-between rounded-xl border p-4 text-left transition ${
                              selected
                                ? "border-amber-600 bg-amber-950/30"
                                : "border-neutral-900 bg-neutral-900/30 hover:border-neutral-800"
                            }`}
                          >
                            <div>
                              <span
                                className={`text-sm font-medium ${selected ? "text-amber-400" : "text-neutral-200"}`}
                              >
                                {a.name}
                              </span>
                              {a.photo_count !== undefined && (
                                <span className="ml-2 text-xs text-neutral-500">
                                  {a.photo_count} photo{a.photo_count !== 1 ? "s" : ""}
                                </span>
                              )}
                            </div>
                            {selected && (
                              <svg className="h-4 w-4 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                            )}
                          </button>
                        );
                      })
                    )}

                    {/* Preview photos in selected album */}
                    {selectedAlbumId && albumPhotos.length > 0 && (
                      <div className="mt-2 rounded-xl border border-neutral-900 bg-neutral-900/30 p-3">
                        <p className="mb-2 text-xs text-neutral-500">
                          Photos in this album (new photos added later will be included automatically)
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {albumPhotos.slice(0, 12).map((p) => (
                            <div
                              key={p.id}
                              className="h-14 w-14 overflow-hidden rounded-lg bg-neutral-800"
                            >
                              {p.has_thumbnail && (
                                <img
                                  src={getPhotoThumbnailUrl(p.id)}
                                  alt={p.filename}
                                  className="h-full w-full object-cover"
                                />
                              )}
                            </div>
                          ))}
                          {albumPhotos.length > 12 && (
                            <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-neutral-800 text-xs text-neutral-500">
                              +{albumPhotos.length - 12}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Time window for album-based shows */}
                    {selectedAlbumId && (
                      <div className="mt-4">
                        <h3 className="text-xs font-medium text-neutral-500">
                          Time Window (optional)
                        </h3>
                        <p className="mt-0.5 text-[11px] text-neutral-600">
                          Filter photos by date. Uses photo date if set, otherwise upload date.
                        </p>
                        <div className="mt-2 grid grid-cols-2 gap-2">
                          {TIME_WINDOWS.map((tw) => {
                            const selected = form.time_window === tw.value;
                            return (
                              <button
                                key={tw.value}
                                onClick={() => setForm({ ...form, time_window: tw.value })}
                                className={`rounded-xl border p-2.5 text-left transition ${
                                  selected
                                    ? "border-amber-600 bg-amber-950/30"
                                    : "border-neutral-900 bg-neutral-900/30 hover:border-neutral-800"
                                }`}
                              >
                                <span
                                  className={`text-xs font-medium ${selected ? "text-amber-400" : "text-neutral-200"}`}
                                >
                                  {tw.label}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="mt-3">
                    {allPhotos.length === 0 ? (
                      <div className="rounded-xl border border-neutral-900 bg-neutral-900/30 p-6 text-center">
                        <p className="text-sm text-neutral-500">No photos uploaded yet.</p>
                        <Link
                          to="/photos"
                          className="mt-2 inline-block text-xs text-amber-500 hover:text-amber-400"
                        >
                          Go to Photo Library to upload some
                        </Link>
                      </div>
                    ) : (
                      <>
                        <p className="mb-2 text-xs text-neutral-500">
                          {selectedPhotoIds.length} photo{selectedPhotoIds.length !== 1 ? "s" : ""} selected
                        </p>
                        <div className="grid max-h-64 grid-cols-4 gap-2 overflow-y-auto sm:grid-cols-6">
                          {allPhotos.map((p) => {
                            const selected = selectedPhotoIds.includes(p.id);
                            return (
                              <button
                                key={p.id}
                                onClick={() => togglePhotoId(p.id)}
                                className={`relative aspect-square overflow-hidden rounded-lg border transition ${
                                  selected
                                    ? "border-amber-500 ring-2 ring-amber-500/30"
                                    : "border-neutral-800 hover:border-neutral-700"
                                }`}
                              >
                                {p.has_thumbnail ? (
                                  <img
                                    src={getPhotoThumbnailUrl(p.id)}
                                    alt={p.filename}
                                    className="h-full w-full object-cover"
                                    loading="lazy"
                                  />
                                ) : (
                                  <div className="flex h-full items-center justify-center bg-neutral-900 text-neutral-700">
                                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                  </div>
                                )}
                                {selected && (
                                  <div className="absolute inset-0 flex items-center justify-center bg-amber-500/20">
                                    <svg className="h-5 w-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                    </svg>
                                  </div>
                                )}
                                {p.ocr_status !== "ready" && (
                                  <div className="absolute bottom-0.5 right-0.5">
                                    <span className={`inline-block rounded px-1 text-[8px] font-medium ${
                                      p.ocr_status === "failed" ? "bg-red-900 text-red-300" : "bg-amber-900 text-amber-300"
                                    }`}>
                                      {p.ocr_status}
                                    </span>
                                  </div>
                                )}
                              </button>
                            );
                          })}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </>
            )}
          </section>
        )}

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
