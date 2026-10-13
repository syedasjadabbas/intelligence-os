import { Ban, Check, CircleCheck, CircleX, Clock, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import type { DocumentStatus } from "@/lib/api";

interface RunStatusLike {
  status: string;
  progress_current?: number | null;
  progress_total?: number | null;
  total_test_cases: number;
}

/** Evaluation run lifecycle badge (PENDING is presented as "Queued"). */
export function RunStatusBadge({
  run,
  showProgress = true,
  size = "sm",
  title,
}: {
  run: RunStatusLike;
  showProgress?: boolean;
  size?: "sm" | "md";
  title?: string;
}) {
  switch (run.status) {
    case "COMPLETED":
      return (
        <Badge tone="success" size={size} title={title}>
          <CircleCheck />
          Completed
        </Badge>
      );
    case "RUNNING":
      return (
        <Badge tone="info" size={size} title={title}>
          <Spinner className="size-3" />
          Running
          {showProgress && run.progress_total ? (
            <span className="tabular font-mono opacity-80">
              {run.progress_current ?? 0}/{run.progress_total}
            </span>
          ) : null}
        </Badge>
      );
    case "PENDING":
      return (
        <Badge tone="warning" size={size} title={title}>
          <Clock />
          Queued
        </Badge>
      );
    case "CANCELLED":
      return (
        <Badge tone="neutral" size={size} title={title}>
          <Ban />
          Cancelled
        </Badge>
      );
    default:
      return (
        <Badge tone="danger" size={size} title={title}>
          <CircleX />
          {run.status === "FAILED" ? "Failed" : run.status}
        </Badge>
      );
  }
}

export function JudgeBadge({ judgeType, long = false }: { judgeType: string; long?: boolean }) {
  return judgeType === "llm" ? (
    <Badge tone="llm" dot>
      LLM Judge
    </Badge>
  ) : (
    <Badge tone="deterministic" dot>
      {long ? "Deterministic Judge" : "Deterministic"}
    </Badge>
  );
}

export function PassFailBadge({ passed }: { passed: boolean }) {
  return passed ? (
    <Badge tone="success">
      <Check />
      Pass
    </Badge>
  ) : (
    <Badge tone="danger">
      <X />
      Fail
    </Badge>
  );
}

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  switch (status) {
    case "COMPLETED":
      return (
        <Badge tone="success" dot>
          Indexed
        </Badge>
      );
    case "PROCESSING":
      return (
        <Badge tone="info" dot pulse>
          Processing
        </Badge>
      );
    case "QUEUED":
      return (
        <Badge tone="warning" dot>
          Queued
        </Badge>
      );
    case "FAILED":
      return (
        <Badge tone="danger" dot>
          Failed
        </Badge>
      );
  }
}

/** Colors a 0–1 pass rate using the dashboard's existing 95% / 80% gates. */
export function passRateTone(rate: number): "success" | "warning" | "danger" {
  return rate >= 0.95 ? "success" : rate >= 0.8 ? "warning" : "danger";
}
