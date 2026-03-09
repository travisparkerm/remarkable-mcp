import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  getSettings,
  updateSettings,
  getRemarkableStatus,
  registerDevice,
  getPersonalities,
  type Settings as SettingsType,
  type Personality,
  type User,
} from "../lib/api";

interface Props {
  user: User;
}

const TIMEZONES = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Europe/Warsaw",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Australia/Sydney",
  "UTC",
];

export default function Settings({ user: _user }: Props) {
  const [settings, setSettings] = useState<SettingsType>({});
  const [personalities, setPersonalities] = useState<Personality[]>([]);
  const [remarkableConnected, setRemarkableConnected] = useState(false);
  const [deviceCode, setDeviceCode] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [connectError, setConnectError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getSettings(), getRemarkableStatus(), getPersonalities()])
      .then(([s, status, p]) => {
        setSettings(s);
        setRemarkableConnected(status.connected);
        setPersonalities(p);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleConnect = async () => {
    if (!deviceCode.trim()) return;
    setConnecting(true);
    setConnectError("");
    try {
      await registerDevice(deviceCode.trim());
      setRemarkableConnected(true);
      setDeviceCode("");
    } catch (err) {
      setConnectError(err instanceof Error ? err.message : "Failed to connect");
    } finally {
      setConnecting(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await updateSettings(settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // handle silently
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

        <h1 className="mt-6 text-2xl font-semibold tracking-tight text-neutral-100">
          Settings
        </h1>

        {/* reMarkable Connection */}
        <section className="mt-8">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            reMarkable Connection
          </h2>
          <div className="mt-4 rounded-xl border border-neutral-900 bg-neutral-900/30 p-5">
            <div className="flex items-center gap-2">
              <div
                className={`h-2 w-2 rounded-full ${remarkableConnected ? "bg-emerald-500" : "bg-neutral-600"}`}
              />
              <span className="text-sm text-neutral-300">
                {remarkableConnected ? "Connected" : "Not connected"}
              </span>
            </div>

            {remarkableConnected && (
              <button
                onClick={async () => {
                  try {
                    const token = localStorage.getItem("session_token");
                    await fetch("/api/remarkable/disconnect", {
                      method: "POST",
                      headers: {
                        ...(token ? { Authorization: `Bearer ${token}` } : {}),
                      },
                    });
                    setRemarkableConnected(false);
                  } catch {}
                }}
                className="mt-3 text-xs text-red-400 transition hover:text-red-300"
              >
                Disconnect device
              </button>
            )}

            {!remarkableConnected && (
              <div className="mt-4 space-y-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={deviceCode}
                    onChange={(e) => setDeviceCode(e.target.value)}
                    placeholder="Enter one-time code"
                    className="flex-1 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-amber-600"
                  />
                  <button
                    onClick={handleConnect}
                    disabled={connecting || !deviceCode.trim()}
                    className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-neutral-950 transition hover:bg-amber-500 disabled:opacity-50"
                  >
                    {connecting ? "Connecting..." : "Connect"}
                  </button>
                </div>
                {connectError && (
                  <p className="text-xs text-red-400">{connectError}</p>
                )}
                <p className="text-xs text-neutral-500">
                  Get a code from{" "}
                  <a
                    href="https://my.remarkable.com/device/desktop/connect"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-amber-500 hover:text-amber-400"
                  >
                    my.remarkable.com/device/desktop/connect
                  </a>
                </p>
              </div>
            )}
          </div>
        </section>

        {/* Podcast Personality */}
        <section className="mt-8">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Podcast Personality
          </h2>
          <p className="mt-1 text-xs text-neutral-600">
            Choose how your daily summary is framed
          </p>
          <div className="mt-4 grid gap-3">
            {personalities.map((p) => {
              const selected = (settings.personality || "analyst") === p.key;
              return (
                <button
                  key={p.key}
                  onClick={() =>
                    setSettings({ ...settings, personality: p.key })
                  }
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
                    <span className="text-xs text-neutral-500">
                      — {p.tagline}
                    </span>
                  </div>
                  <p className="mt-1.5 pl-4 text-xs text-neutral-500">
                    {p.description}
                  </p>
                </button>
              );
            })}
          </div>
        </section>

        {/* Voice & Style */}
        <section className="mt-8">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Voice & Style
          </h2>
          <div className="mt-4 space-y-4 rounded-xl border border-neutral-900 bg-neutral-900/30 p-5">
            <div>
              <label className="block text-sm text-neutral-400">
                ElevenLabs Voice ID
              </label>
              <input
                type="text"
                value={settings.elevenlabs_voice_id ?? ""}
                onChange={(e) =>
                  setSettings({ ...settings, elevenlabs_voice_id: e.target.value })
                }
                placeholder="e.g. 21m00Tcm4TlvDq8ikWAM"
                className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-amber-600"
              />
            </div>

            <div>
              <label className="block text-sm text-neutral-400">
                Target word count
              </label>
              <input
                type="number"
                value={settings.target_word_count ?? ""}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    target_word_count: e.target.value
                      ? parseInt(e.target.value)
                      : undefined,
                  })
                }
                placeholder="350"
                className="mt-1 w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-amber-600"
              />
            </div>
          </div>
        </section>

        {/* Timezone */}
        <section className="mt-8">
          <h2 className="text-sm font-medium uppercase tracking-wider text-neutral-500">
            Timezone
          </h2>
          <div className="mt-4 rounded-xl border border-neutral-900 bg-neutral-900/30 p-5">
            <select
              value={settings.timezone ?? ""}
              onChange={(e) =>
                setSettings({ ...settings, timezone: e.target.value })
              }
              className="w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-amber-600"
            >
              <option value="">Select timezone</option>
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
          </div>
        </section>

        {/* Save */}
        <div className="mt-8 flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-amber-600 px-6 py-2.5 text-sm font-medium text-neutral-950 transition hover:bg-amber-500 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
          {saved && (
            <span className="text-sm text-emerald-400">Saved</span>
          )}
        </div>
      </div>
    </div>
  );
}
