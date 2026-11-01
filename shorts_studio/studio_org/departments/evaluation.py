"""평가부: 기술검수 · 대본화면일치 · 성과분석.

Three separate judgments, never collapsed into one verdict:

  technical_qa          -- did the artifact pass the existing, unmodified
                            technical gates (shorts_studio.factory.
                            curious_mechanics_native_qa.verify, etc.)?
  content_screen_match   -- does what's on screen actually match what the
                            script/requirement says should be there (this is
                            the same judgment the narration/scene audit made
                            by hand earlier in this project; here it is a
                            task the evaluation department runs)?
  performance_analysis   -- how did it actually perform once published?
                            Always UNVERIFIED here: this project does not
                            publish publicly, so there is never real
                            performance data, and that fact is reported
                            honestly rather than guessed at or omitted.
"""
from __future__ import annotations

from pathlib import Path

from ..ledger import TaskLedger
from ..task import Task

MOCK_TECHNICAL_QA_STATUS = "MOCK_SKIPPED"  # never the real PASS_NATIVE_ORIGINAL_SHARD string


class EvaluationDept:
    def technical_qa(self, render_task: Task) -> dict:
        output = render_task.output or {}
        if output.get("is_mock"):
            return {"status": MOCK_TECHNICAL_QA_STATUS,
                     "detail": "mock task carries no rendered frames to verify"}
        return self._technical_qa_real(render_task)

    @staticmethod
    def _technical_qa_real(render_task: Task) -> dict:
        """Real connection: shorts_studio.factory.curious_mechanics_native_qa.verify.

        Not exercised by this round's tests -- it requires an actual
        rendered-frame directory, manifest, and renderer file on disk, which
        only exist as GitHub Actions artifacts, not in this sandbox.
        """
        from shorts_studio.factory.curious_mechanics_native_qa import verify

        output = render_task.output or {}
        try:
            out_dir = Path(output["out_dir"])
            manifest = Path(output["manifest"])
            renderer = Path(output["renderer"])
        except KeyError as exc:
            raise ValueError(
                "real technical_qa requires output.out_dir/manifest/renderer"
            ) from exc
        result = verify(out_dir, manifest, renderer)
        return {"status": result["status"], "detail": result}

    def content_screen_match(self, render_task: Task, requirement: dict) -> dict:
        output = render_task.output or {}
        if output.get("is_mock"):
            matches = render_task.requirements.get("shot") == requirement.get("shot")
            return {"status": "PASS" if matches else "FAIL", "mock": True}
        raise NotImplementedError(
            "real content_screen_match would call benchmarks.road_safety."
            "curious_mechanics_delivery.semantic(); not implemented here"
        )

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
            failure_reason=None if passed else "technical_qa or content_screen_match failed",
            is_mock=render_task.is_mock,
        )
