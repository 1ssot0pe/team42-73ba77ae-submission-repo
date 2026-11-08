/**
 * Pre-dosing approvals for the workspace stages. Placeholder owned by fixer F1 (fix round 1):
 * Design review groups the protocol fix approvals; the clinician shortlist stays a separate approval.
 */
import { ApprovalInbox } from "../shared";

export function PredoseApprovals({ only }: { only?: "design" | "recruitment" | "screening" }) {
  void only;
  return <ApprovalInbox module="predose" title="Approvals" signedLimit={4} />;
}
