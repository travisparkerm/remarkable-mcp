import { useEffect, useState, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  getAlbums,
  getPhotos,
  createAlbum,
  deleteAlbum,
  updateAlbum,
  uploadPhotos,
  updatePhoto,
  deletePhoto,
  retryPhotoOcr,
  batchUpdatePhotos,
  getPhotoThumbnailUrl,
  getPhotoImageUrl,
  type Album,
  type PhotoRecord,
} from "../lib/api";

const OCR_STATUS_STYLES: Record<string, string> = {
  ready: "bg-emerald-900/50 text-emerald-400",
  processing: "bg-amber-900/50 text-amber-400",
  pending: "bg-neutral-800 text-neutral-400",
  failed: "bg-red-900/50 text-red-400",
};

function OcrBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${
        OCR_STATUS_STYLES[status] ?? OCR_STATUS_STYLES.pending
      }`}
    >
      {status}
    </span>
  );
}

export default function PhotoLibrary() {
  const [albums, setAlbums] = useState<Album[]>([]);
  const [photos, setPhotos] = useState<PhotoRecord[]>([]);
  const [selectedAlbum, setSelectedAlbum] = useState<number | null>(null); // null = all, 0 = unsorted
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedPhotos, setSelectedPhotos] = useState<Set<number>>(new Set());
  const [detailPhoto, setDetailPhoto] = useState<PhotoRecord | null>(null);
  const [newAlbumName, setNewAlbumName] = useState("");
  const [showNewAlbum, setShowNewAlbum] = useState(false);
  const [editingAlbum, setEditingAlbum] = useState<number | null>(null);
  const [editAlbumName, setEditAlbumName] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragRef = useRef<HTMLDivElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [a, p] = await Promise.all([
        getAlbums(),
        getPhotos(selectedAlbum ?? undefined),
      ]);
      setAlbums(a);
      setPhotos(p);
    } catch {
    } finally {
      setLoading(false);
    }
  }, [selectedAlbum]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll for OCR status updates
  useEffect(() => {
    const hasPending = photos.some(
      (p) => p.ocr_status === "pending" || p.ocr_status === "processing"
    );
    if (!hasPending) return;

    const interval = setInterval(async () => {
      const fresh = await getPhotos(selectedAlbum ?? undefined);
      setPhotos(fresh);
    }, 3000);

    return () => clearInterval(interval);
  }, [photos, selectedAlbum]);

  const handleUpload = async (files: FileList | File[]) => {
    setUploading(true);
    try {
      await uploadPhotos(
        files,
        selectedAlbum && selectedAlbum > 0 ? selectedAlbum : undefined
      );
      await fetchData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      handleUpload(e.dataTransfer.files);
    }
  };

  const handleCreateAlbum = async () => {
    if (!newAlbumName.trim()) return;
    await createAlbum({ name: newAlbumName.trim() });
    setNewAlbumName("");
    setShowNewAlbum(false);
    await fetchData();
  };

  const handleDeleteAlbum = async (id: number) => {
    if (!confirm("Delete this album? Photos will be moved to Unsorted.")) return;
    await deleteAlbum(id);
    if (selectedAlbum === id) setSelectedAlbum(null);
    await fetchData();
  };

  const handleRenameAlbum = async (id: number) => {
    if (!editAlbumName.trim()) return;
    await updateAlbum(id, { name: editAlbumName.trim() });
    setEditingAlbum(null);
    setEditAlbumName("");
    await fetchData();
  };

  const handleDeletePhoto = async (id: number) => {
    if (!confirm("Delete this photo permanently?")) return;
    await deletePhoto(id);
    setDetailPhoto(null);
    setSelectedPhotos((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
    await fetchData();
  };

  const handleBatchMove = async (albumId: number | null) => {
    await batchUpdatePhotos({
      photo_ids: Array.from(selectedPhotos),
      album_id: albumId,
    });
    setSelectedPhotos(new Set());
    await fetchData();
  };

  const togglePhotoSelect = (id: number) => {
    setSelectedPhotos((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
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
      <div className="mx-auto max-w-4xl px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
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
              Home
            </Link>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight text-neutral-100">
              Photo Library
            </h1>
          </div>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-neutral-950 transition hover:bg-amber-500 disabled:opacity-50"
          >
            {uploading ? "Uploading..." : "Upload Photos"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/*,.heic,.heif"
            className="hidden"
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                handleUpload(e.target.files);
              }
              // Reset so the same file can be selected again
              e.target.value = "";
            }}
          />
        </div>

        {/* Album tabs */}
        <div className="mt-6 flex items-center gap-2 overflow-x-auto pb-2">
          <button
            onClick={() => setSelectedAlbum(null)}
            className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              selectedAlbum === null
                ? "bg-amber-600 text-neutral-950"
                : "bg-neutral-900 text-neutral-400 hover:text-neutral-200"
            }`}
          >
            All Photos
          </button>
          <button
            onClick={() => setSelectedAlbum(0)}
            className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              selectedAlbum === 0
                ? "bg-amber-600 text-neutral-950"
                : "bg-neutral-900 text-neutral-400 hover:text-neutral-200"
            }`}
          >
            Unsorted
          </button>
          {albums.map((a) => (
            <div key={a.id} className="group relative shrink-0">
              {editingAlbum === a.id ? (
                <div className="flex items-center gap-1">
                  <input
                    type="text"
                    value={editAlbumName}
                    onChange={(e) => setEditAlbumName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleRenameAlbum(a.id)}
                    className="w-28 rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs text-neutral-200 outline-none"
                    autoFocus
                  />
                  <button
                    onClick={() => handleRenameAlbum(a.id)}
                    className="text-xs text-amber-500"
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingAlbum(null)}
                    className="text-xs text-neutral-500"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setSelectedAlbum(a.id)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                    selectedAlbum === a.id
                      ? "bg-amber-600 text-neutral-950"
                      : "bg-neutral-900 text-neutral-400 hover:text-neutral-200"
                  }`}
                >
                  {a.name}
                  {a.photo_count !== undefined && (
                    <span className="ml-1 text-[10px] opacity-60">
                      ({a.photo_count})
                    </span>
                  )}
                </button>
              )}
              {/* Album context menu on hover */}
              {selectedAlbum === a.id && editingAlbum !== a.id && (
                <div className="absolute right-0 top-full z-10 mt-1 flex gap-1">
                  <button
                    onClick={() => {
                      setEditingAlbum(a.id);
                      setEditAlbumName(a.name);
                    }}
                    className="rounded bg-neutral-800 px-2 py-0.5 text-[10px] text-neutral-400 hover:text-neutral-200"
                  >
                    Rename
                  </button>
                  <button
                    onClick={() => handleDeleteAlbum(a.id)}
                    className="rounded bg-neutral-800 px-2 py-0.5 text-[10px] text-red-400 hover:text-red-300"
                  >
                    Delete
                  </button>
                </div>
              )}
            </div>
          ))}
          {showNewAlbum ? (
            <div className="flex items-center gap-1">
              <input
                type="text"
                value={newAlbumName}
                onChange={(e) => setNewAlbumName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreateAlbum()}
                placeholder="Album name"
                className="w-32 rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs text-neutral-200 placeholder-neutral-600 outline-none"
                autoFocus
              />
              <button
                onClick={handleCreateAlbum}
                className="text-xs text-amber-500"
              >
                Create
              </button>
              <button
                onClick={() => setShowNewAlbum(false)}
                className="text-xs text-neutral-500"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowNewAlbum(true)}
              className="shrink-0 rounded-lg border border-dashed border-neutral-700 px-3 py-1.5 text-xs text-neutral-500 transition hover:border-amber-600 hover:text-amber-400"
            >
              + Album
            </button>
          )}
        </div>

        {/* Batch actions */}
        {selectedPhotos.size > 0 && (
          <div className="mt-4 flex items-center gap-3 rounded-lg border border-neutral-800 bg-neutral-900/50 px-4 py-2">
            <span className="text-xs text-neutral-400">
              {selectedPhotos.size} selected
            </span>
            <select
              onChange={(e) => {
                const val = e.target.value;
                if (val === "") return;
                handleBatchMove(val === "unsorted" ? null : Number(val));
                e.target.value = "";
              }}
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs text-neutral-300 outline-none"
              defaultValue=""
            >
              <option value="" disabled>
                Move to...
              </option>
              <option value="unsorted">Unsorted</option>
              {albums.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
            <button
              onClick={() => setSelectedPhotos(new Set())}
              className="text-xs text-neutral-500 hover:text-neutral-300"
            >
              Clear selection
            </button>
          </div>
        )}

        {/* Drop zone + Photo grid */}
        <div
          ref={dragRef}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`mt-4 min-h-[200px] rounded-xl border-2 border-dashed transition ${
            dragOver
              ? "border-amber-500 bg-amber-950/10"
              : "border-transparent"
          }`}
        >
          {photos.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20">
              <svg
                className="h-12 w-12 text-neutral-700"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              <p className="mt-3 text-sm text-neutral-500">
                Drop photos here or click Upload
              </p>
              <p className="mt-1 text-xs text-neutral-600">
                Supports JPEG, PNG, and HEIC
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5">
              {photos.map((p) => (
                <div
                  key={p.id}
                  className={`group relative cursor-pointer overflow-hidden rounded-lg border transition ${
                    selectedPhotos.has(p.id)
                      ? "border-amber-500 ring-2 ring-amber-500/30"
                      : "border-neutral-800 hover:border-neutral-700"
                  }`}
                >
                  {/* Selection checkbox */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      togglePhotoSelect(p.id);
                    }}
                    className={`absolute left-1.5 top-1.5 z-10 flex h-5 w-5 items-center justify-center rounded border transition ${
                      selectedPhotos.has(p.id)
                        ? "border-amber-500 bg-amber-500 text-black"
                        : "border-neutral-600 bg-neutral-900/80 text-transparent group-hover:text-neutral-400"
                    }`}
                  >
                    <svg
                      className="h-3 w-3"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={3}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  </button>

                  {/* Thumbnail */}
                  <div
                    onClick={() => setDetailPhoto(p)}
                    className="aspect-square bg-neutral-900"
                  >
                    {p.has_thumbnail ? (
                      <img
                        src={getPhotoThumbnailUrl(p.id)}
                        alt={p.filename}
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center text-neutral-700">
                        <svg
                          className="h-8 w-8"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={1.5}
                            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                          />
                        </svg>
                      </div>
                    )}
                  </div>

                  {/* OCR status + date */}
                  <div className="flex items-center justify-between bg-neutral-900 px-2 py-1">
                    <OcrBadge status={p.ocr_status} />
                    {p.user_date && (
                      <span className="text-[10px] text-neutral-500">
                        {p.user_date}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Photo detail modal */}
        {detailPhoto && (
          <PhotoDetailModal
            photo={detailPhoto}
            albums={albums}
            onClose={() => setDetailPhoto(null)}
            onUpdate={async (data) => {
              await updatePhoto(detailPhoto.id, data);
              await fetchData();
              // Refresh detail
              const fresh = await getPhotos(selectedAlbum ?? undefined);
              setPhotos(fresh);
              const updated = fresh.find((p) => p.id === detailPhoto.id);
              if (updated) setDetailPhoto(updated);
            }}
            onDelete={() => handleDeletePhoto(detailPhoto.id)}
            onRetryOcr={async () => {
              await retryPhotoOcr(detailPhoto.id);
              setDetailPhoto({ ...detailPhoto, ocr_status: "pending" });
              await fetchData();
            }}
          />
        )}
      </div>
    </div>
  );
}

function PhotoDetailModal({
  photo,
  albums,
  onClose,
  onUpdate,
  onDelete,
  onRetryOcr,
}: {
  photo: PhotoRecord;
  albums: Album[];
  onClose: () => void;
  onUpdate: (data: Record<string, unknown>) => Promise<void>;
  onDelete: () => void;
  onRetryOcr: () => Promise<void>;
}) {
  const [userDate, setUserDate] = useState(photo.user_date || "");
  const [userNotes, setUserNotes] = useState(photo.user_notes || "");
  const [editingOcr, setEditingOcr] = useState(false);
  const [ocrText, setOcrText] = useState(photo.ocr_text || "");

  useEffect(() => {
    setUserDate(photo.user_date || "");
    setUserNotes(photo.user_notes || "");
    setOcrText(photo.ocr_text || "");
    setEditingOcr(false);
  }, [photo]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
    >
      <div
        className="relative max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-neutral-800 bg-neutral-950 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-neutral-500 hover:text-neutral-300"
        >
          <svg
            className="h-5 w-5"
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
        </button>

        <div className="grid gap-6 md:grid-cols-2">
          {/* Image */}
          <div>
            <img
              src={getPhotoImageUrl(photo.id)}
              alt={photo.filename}
              className="w-full rounded-lg"
            />
            <p className="mt-2 text-xs text-neutral-500">{photo.filename}</p>
          </div>

          {/* Details */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <OcrBadge status={photo.ocr_status} />
              {(photo.ocr_status === "failed" ||
                photo.ocr_status === "ready") && (
                <button
                  onClick={onRetryOcr}
                  className="text-xs text-amber-500 hover:text-amber-400"
                >
                  Retry OCR
                </button>
              )}
            </div>

            {/* OCR Text */}
            <div>
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-neutral-500">
                  OCR Text
                </label>
                {photo.ocr_status === "ready" && (
                  <button
                    onClick={() => setEditingOcr(!editingOcr)}
                    className="text-xs text-neutral-500 hover:text-neutral-300"
                  >
                    {editingOcr ? "Cancel" : "Edit"}
                  </button>
                )}
              </div>
              {editingOcr ? (
                <div className="mt-1">
                  <textarea
                    value={ocrText}
                    onChange={(e) => setOcrText(e.target.value)}
                    rows={8}
                    className="w-full rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-2 text-xs text-neutral-200 outline-none focus:border-amber-600"
                  />
                  <button
                    onClick={async () => {
                      await onUpdate({ ocr_text: ocrText });
                      setEditingOcr(false);
                    }}
                    className="mt-1 rounded bg-amber-600 px-3 py-1 text-xs font-medium text-neutral-950"
                  >
                    Save OCR Text
                  </button>
                </div>
              ) : (
                <div className="mt-1 max-h-48 overflow-y-auto rounded-lg bg-neutral-900 p-3 text-xs text-neutral-300">
                  {photo.ocr_text || (
                    <span className="italic text-neutral-600">
                      {photo.ocr_status === "pending" || photo.ocr_status === "processing"
                        ? "OCR in progress..."
                        : "No text extracted"}
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Date */}
            <div>
              <label className="text-xs font-medium text-neutral-500">
                Date (optional)
              </label>
              <input
                type="date"
                value={userDate}
                onChange={(e) => setUserDate(e.target.value)}
                onBlur={() => onUpdate({ user_date: userDate || null })}
                className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-amber-600"
              />
            </div>

            {/* Notes */}
            <div>
              <label className="text-xs font-medium text-neutral-500">
                Notes (optional)
              </label>
              <textarea
                value={userNotes}
                onChange={(e) => setUserNotes(e.target.value)}
                onBlur={() => onUpdate({ user_notes: userNotes || null })}
                rows={2}
                placeholder="e.g., 'Prayer journal, March 5'"
                className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-600 outline-none focus:border-amber-600"
              />
            </div>

            {/* Album */}
            <div>
              <label className="text-xs font-medium text-neutral-500">
                Album
              </label>
              <select
                value={photo.album_id ?? ""}
                onChange={(e) => {
                  const val = e.target.value;
                  onUpdate({
                    album_id: val ? Number(val) : 0,
                  });
                }}
                className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-xs text-neutral-200 outline-none focus:border-amber-600"
              >
                <option value="">Unsorted</option>
                {albums.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Delete */}
            <button
              onClick={onDelete}
              className="mt-4 rounded-lg border border-red-900/50 px-3 py-1.5 text-xs text-red-400 transition hover:bg-red-950/30"
            >
              Delete Photo
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
