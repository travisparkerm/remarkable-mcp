import { getStatusStyle, getStatusLabel } from "../lib/constants";

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusStyle(status)}`}
    >
      {getStatusLabel(status)}
    </span>
  );
}
