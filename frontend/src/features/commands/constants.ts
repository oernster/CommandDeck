import type { StageId, Status } from "../../api/commands";

export const STAGES: StageId[] = ["DESIGN", "BUILD", "REVIEW", "COMPLETE"];

export const DEFAULT_STAGE_LABELS: Record<StageId, string> = {
  DESIGN: "Design",
  BUILD: "Build",
  REVIEW: "Review",
  COMPLETE: "Complete",
};

export const STATUSES: Status[] = [
  "Not Started",
  "In Progress",
  "Blocked",
  "Complete",
];

