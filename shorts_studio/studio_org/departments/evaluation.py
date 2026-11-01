"""평가부: 기술검수 · 대본화면일치 · 성과분석.

Three separate judgments, never collapsed into one verdict:

  technical_qa          -- did the artifact pass the existing, unmodified
                            technical gates (shorts_studio.factory.
                            curious_mechanics_native_qa.verify, etc.)?
                            For a real (non-mock) render task this relays the
                            verdict that already ran server-side, inside the
                            GitHub Actions job that rendered it -- see
                            render.py's module docstring for why this is not
                            recomputed locally.
  content_screen_match   -- does what's on screen actually match what the
                            script/requirement says should be there? Real
                            connection (benchmarks.road_safety.
                            curious_mechanics_delivery.semantic) requires a
                            fully assembled clip with audio, which a single
                            preview-frame render never produces, so this is
                            explicitly NOT_IMPLEMENTED for real tasks rather
                            than silently skipped or faked.
  performance_analysis   -- how did it actually perform once published?
                            Always UNVERIFIED here: this project does not
                            publish publicly, so there is never real
                            performance data, and that fact is reported
                            honestly rather than guessed at or omitted.
"""
from __future__ import annotations

from ..ledger import TaskLedger
from ..task import Task

MOCK_TECHNICAL_QA_STATUS = "MOCK_SKIPPED"  # never the real PASS_NATIVE_ORIGINAL_SHARD string
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class EvaluationDept:
    def technical_qa(self, render_task: Task) -> dict:
        output = render_task.output or {}
        if output.get("is_mock"):
            return {"status": MOCK_TECHNICAL_QA_STATUS,
                     "detail": "mock task carries no rendered frames to verify"}
        return self._technical_qa_real(render_task)

    @staticmethod
    def _technical_qa_real(render_task: Task) -> dict:
        """Relays the real curious_mechanics_native_qa.verify() verdict that
        studio-org-render-task.yml already computed server-side (see
        render.py's RenderDept._execute_real / fetch_eval_result). A preview
        render is expected to genuinely FAIL this check (preview_only=True,
        450x800/7 samples vs the production contract's False/1080x1920/32) --
        that is the real, unmodified gate working correctly, not a bug."""
        payload = (render_task.output or {}).get("real_technical_qa")
        if payload is None:
            raise ValueError(
                f"render task {render_task.task_id} has no embedded "
                "real_technical_qa result to relay"
            )
        if payload.get("ok"):
            return {"status": payload["result"]["status"], "detail": payload["result"]}
        return {"status": "FAIL",
                 "detail": f"{payload['error_type']}: {payload['error']}"}

    def content_screen_match(self, render_task: Task, requirement: dict) -> dict:
        output = render_task.output or {}
        if output.get("is_mock"):
            matches = render_task.requirements.get("shot") == requirement.get("shot")
            return {"status": "PASS" if matches else "FAIL", "mock": True}
        return {
            "status": NOT_IMPLEMENTED,
            "reason": "requires benchmarks.road_safety.curious_mechanics_delivery.semantic() "
                      "against a fully assembled clip with audio; a single preview-frame "
                      "render has no assembled output to check this against",
        }

    def performance_analysis(self, render_task: Task) -> dict:
        return {
            "status": "UNVERIFIED",
            "reason": "no publish/performance data available (no public upload performed)",
        }

    def evaluate(self, render_task: Task, requirement: dict, ledger: TaskLedger) -> Task:
        technical = self.technical_qa(render_task)
        content = self.content_screen_match(render_task, requirement)
        performance = self.performance_analysis(render_task)
        passed = (
            technical["status"] in ("PASS", MOCK_TECHNICAL_QA_STATUS)
            and content["status"] == "PASS"
        )
        if content["status"] == NOT_IMPLEMENTED:
            failure_reason = "content_screen_match is not implemented for real render tasks"
        elif not passed:
            failure_reason = "technical_qa or content_screen_match failed"
        else:
            failure_reason = None
        return ledger.create(
            department="평가부", division="기술검수",
            requirements=requirement, predecessors=[render_task.task_id],
            input_hash=render_task.input_hash,
            output={
                "technical_qa": technical,
                "content_screen_match": content,
                "performance_analysis": performance,
            },
            completion_criteria="technical_qa and content_screen_match both PASS",
            status="completed" if passed else "failed",
            failure_reason=failure_reason,
            is_mock=render_task.is_mock,
        )
