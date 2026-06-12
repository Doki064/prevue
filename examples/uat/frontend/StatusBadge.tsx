type StatusBadgeProps = {
  status: "pass" | "fail" | "pending";
};

const LABELS: Record<StatusBadgeProps["status"], string> = {
  pass: "Passed",
  fail: "Failed",
  pending: "Pending",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return <span className={`badge badge-${status}`}>{LABELS[status]}</span>;
}
