"""Regression coverage for the compact real-social runtime contract."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


BUNDLE = Path(__file__).resolve().parents[1]
ROUTE_SCRIPT = BUNDLE / "scripts" / "route_request.py"
PHRASE_SCRIPT = BUNDLE / "scripts" / "search_phrases.py"
ROUTE_INDEX = BUNDLE / "runtime" / "route-index.json"
ROUTE_CONFIG = BUNDLE / "knowledge" / "04-系统" / "真实社交运行时路由配置.json"
RUNTIME_ENTRY = BUNDLE / "runtime" / "runtime-entry.md"


def run_json(script: Path, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=BUNDLE,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class RuntimeRoutingTests(unittest.TestCase):
    def test_stage_navigation_principle_precedes_output_format(self) -> None:
        skill_text = (BUNDLE / "SKILL.md").read_text(encoding="utf-8")
        navigation = re.search(
            r"^##+\s+阶段导航优先原则\s*$", skill_text, flags=re.MULTILINE
        )
        output = re.search(r"^##+\s+输出格式\s*$", skill_text, flags=re.MULTILINE)
        self.assertIsNotNone(navigation)
        self.assertIsNotNone(output)
        assert navigation is not None
        assert output is not None
        self.assertLess(navigation.start(), output.start())
        for term in (
            "observed",
            "reported",
            "inferred",
            "当前阶段节点",
            "候选分链",
            "状态路由",
            "反馈",
            "机械延续",
        ):
            self.assertIn(term, skill_text)

    def test_reply_examples_require_context_before_phrase_retrieval(self) -> None:
        no_request = run_json(ROUTE_SCRIPT, "--text", "分析这段聊天")
        self.assertEqual(no_request["task_route"]["id"], "analyze_chat")
        self.assertEqual(
            no_request["read_plan"]["phrase_retrieval"],
            "disabled_until_reply_request",
        )

        no_context = run_json(
            ROUTE_SCRIPT,
            "--text",
            "直接帮我回复",
            "--task-route",
            "reply_request",
        )
        self.assertEqual(no_context["state_route"]["id"], "unknown_stage")
        self.assertEqual(
            no_context["read_plan"]["phrase_retrieval"],
            "disabled_until_context",
        )

        ready_for_review = run_json(
            ROUTE_SCRIPT,
            "--text",
            "直接帮我回复，当前适合推",
            "--task-route",
            "reply_request",
            "--state-route",
            "interest_push_pull",
            "--direction",
            "push",
            "--engagement",
            "reciprocal",
            "--comfort",
            "comfortable",
        )
        self.assertEqual(ready_for_review["state_route"]["id"], "interest_push_pull")
        self.assertEqual(
            ready_for_review["read_plan"]["phrase_retrieval"],
            "enabled_after_context_review",
        )

    def test_new_feedback_recomputes_direction_instead_of_reusing_previous_push(self) -> None:
        positive = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她继续主动提问和互动舒服",
            "--previous-direction",
            "push",
            "--post-push-feedback",
            "positive",
            "--engagement",
            "reciprocal",
            "--comfort",
            "comfortable",
        )
        self.assertEqual(positive["runtime_fields"]["tactical_direction"], "pull")

        new_feedback = run_json(
            ROUTE_SCRIPT,
            "--text",
            "收到新反馈，她的回应变得含糊",
            "--previous-direction",
            "push",
            "--post-push-feedback",
            "ambiguous",
        )
        self.assertEqual(new_feedback["state_route"]["id"], "interest_push_pull")
        self.assertIsNone(new_feedback["runtime_fields"]["tactical_direction"])
        self.assertEqual(
            new_feedback["runtime_fields"]["planned_pull_status"],
            "blocked",
        )
        self.assertNotEqual(
            new_feedback["runtime_fields"]["tactical_direction"],
            positive["runtime_fields"]["tactical_direction"],
        )

    def test_default_analysis_is_lazy(self) -> None:
        result = run_json(ROUTE_SCRIPT, "--text", "分析这段聊天")
        self.assertEqual(result["task_route"]["id"], "analyze_chat")
        self.assertEqual(result["state_route"]["id"], "unknown_stage")
        self.assertEqual(result["primary_module"], "analyze_chat")
        self.assertEqual(
            result["runtime_fields"]["phrase_retrieval"],
            "disabled_until_reply_request",
        )

    def test_stop_boundary_overrides_explicit_interest_route(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "不要再联系我，推还是拉都不重要",
            "--state-route",
            "interest_push_pull",
            "--direction",
            "push",
        )
        self.assertEqual(result["state_route"]["id"], "stop_boundary")
        self.assertEqual(result["primary_module"], "stop_boundary")
        self.assertEqual(result["runtime_fields"]["phrase_retrieval"], "boundary_only")
        self.assertFalse(result["runtime_fields"]["recontact_permitted"])

    def test_block_and_hide_signals_are_stop_boundary(self) -> None:
        for text in ("她说拉黑我", "她把我屏蔽了", "被拉黑", "被屏蔽"):
            with self.subTest(text=text):
                result = run_json(ROUTE_SCRIPT, "--text", text)
                self.assertEqual(result["state_route"]["id"], "stop_boundary")
                self.assertFalse(result["runtime_fields"]["recontact_permitted"])

    def test_negated_block_mention_is_not_stop_boundary(self) -> None:
        result = run_json(ROUTE_SCRIPT, "--text", "她没有拉黑我")
        self.assertNotEqual(result["state_route"]["id"], "stop_boundary")

    def test_safety_precedes_general_concern(self) -> None:
        for text in ("安全", "她说担心安全，最近很忙"):
            with self.subTest(text=text):
                result = run_json(ROUTE_SCRIPT, "--text", text)
                self.assertEqual(
                    result["state_route"]["id"],
                    "privacy_safety_age_consent",
                )
                self.assertEqual(
                    result["runtime_fields"]["phrase_retrieval"],
                    "disabled_until_verified",
                )

    def test_recovery_disables_phrase_retrieval(self) -> None:
        result = run_json(ROUTE_SCRIPT, "--text", "我很焦虑，忍不住追问")
        self.assertEqual(result["state_route"]["id"], "recovery")
        self.assertEqual(result["runtime_fields"]["recovery_gate"], "can_return_blue")
        self.assertEqual(result["runtime_fields"]["phrase_retrieval"], "disabled")
        self.assertFalse(result["runtime_fields"]["recontact_permitted"])

        search = run_json(PHRASE_SCRIPT, "--route", "recovery", "--query", "回蓝")
        self.assertEqual(search["retrieval_status"], "disabled")
        self.assertEqual(search["matches"], [])

    def test_push_pull_route_exposes_conditional_combination_logic(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她开始推你的时候，推回去后下一步怎么拉",
        )
        self.assertEqual(result["state_route"]["id"], "interest_push_pull")
        self.assertEqual(result["state_route"]["allowed_directions"], ["push", "pull"])
        logic = result["state_route"]["push_pull_logic"]
        self.assertEqual(
            logic["push_back_eligible"]["requires"],
            [
                "playful_challenge_or_light_disagreement",
                "continued_voluntary_engagement",
                "no_boundary_or_discomfort_signal",
            ],
        )
        self.assertEqual(logic["post_push_check"], "required")
        self.assertEqual(logic["pull_after_push"], "preferred_if_positive_feedback")
        self.assertEqual(logic["roller_coaster_goal"], "forbidden")
        self.assertEqual(
            logic["romantic_intent_anchor"]["fixed_turn_count"],
            "forbidden",
        )
        self.assertTrue(
            logic["affect_engagement_policy"]["neutral_affect_is_not_low_response"]
        )
        self.assertEqual(
            logic["direction_bias"]["when_both_eligible"],
            "prefer_push",
        )
        self.assertEqual(
            logic["direction_bias"]["ratio_policy"],
            "qualitative_preference_not_fixed_quota",
        )
        self.assertTrue(logic["planned_pull"]["prepare_with_push"])
        self.assertEqual(
            logic["initial_false_evaluation_order"]["required_order"],
            "push_then_feedback_gated_pull",
        )
        self.assertEqual(
            logic["initial_false_evaluation_order"]["pull_before_push"],
            "forbidden",
        )
        self.assertFalse(
            logic["initial_false_evaluation_order"]["automatic_pull"]
        )
        fields = result["runtime_fields"]
        self.assertEqual(fields["push_back_eligible"], "unknown")
        self.assertEqual(fields["post_push_check"], "required")
        self.assertEqual(fields["pull_after_push"], "preferred_if_positive_feedback")
        self.assertEqual(fields["push_purpose"], "light_tension_and_feedback")
        self.assertEqual(fields["roller_coaster_goal"], "forbidden")
        constraints = fields["tactical_action_constraints"]
        self.assertEqual(constraints["scope"], "interest_push_pull_only")
        self.assertEqual(constraints["status"], "forbidden_in_push_pull")
        self.assertEqual(
            constraints["disallowed"],
            [
                "over_explaining",
                "defensive_justification",
                "performative_apology",
                "strategic_concession",
                "appeasement_or_boundary_abandonment",
            ],
        )
        self.assertEqual(
            constraints["allowed_only_outside_tactical"],
            [
                "truthful_clarification",
                "genuine_apology",
                "boundary_respecting_adjustment",
            ],
        )
        self.assertEqual(
            constraints["redirect_on"],
            {
                "factual_error_or_harm": "clarify",
                "explicit_discomfort_or_stop": "stop_boundary",
                "safety_consent_age": "privacy_safety_age_consent",
                "logistics_or_mutual_negotiation": "concern_condition",
            },
        )

    def test_flat_but_engaged_prefers_push_not_low_response(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她没有情绪，但仍然主动提问和延展",
        )
        self.assertEqual(result["state_route"]["id"], "interest_push_pull")
        fields = result["runtime_fields"]
        self.assertEqual(fields["affect_state"], "neutral")
        self.assertEqual(fields["engagement_state"], "reciprocal")
        self.assertTrue(fields["flat_but_engaged"])
        self.assertEqual(fields["direction_preference"], "push")
        self.assertEqual(fields["planned_pull_status"], "not_applicable")
        self.assertIn(
            "flat_but_engaged_push_preferred",
            result["safety_flags"],
        )

    def test_romantic_intent_drift_reanchors_without_fixed_turn_count(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "聊了几轮已经聊成朋友，但双方仍主动延展，怎么回到恋爱方向",
        )
        self.assertEqual(result["state_route"]["id"], "interest_push_pull")
        fields = result["runtime_fields"]
        self.assertEqual(fields["intent_alignment"], "drifted")
        self.assertEqual(
            fields["romantic_intent_anchor"]["fixed_turn_count"],
            "forbidden",
        )
        self.assertIn(
            "romantic_intent_reanchor_without_fixed_turn_count",
            result["safety_flags"],
        )
        self.assertTrue(fields["romantic_reanchor_permitted"])

    def test_friend_only_boundary_blocks_push_and_reanchor(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她明确说只想做朋友，不考虑恋爱，我还要继续推吗",
            "--state-route",
            "interest_push_pull",
            "--direction",
            "push",
        )
        self.assertEqual(result["state_route"]["id"], "clarify")
        self.assertIsNone(result["runtime_fields"]["tactical_direction"])
        self.assertEqual(
            result["runtime_fields"]["intent_alignment"],
            "friend_only_boundary",
        )
        self.assertFalse(
            result["runtime_fields"]["romantic_reanchor_permitted"]
        )
        self.assertEqual(
            result["runtime_fields"]["intent_boundary_reason"],
            "friend_only_declared",
        )
        self.assertIn(
            "friend_only_boundary_blocks_romantic_reanchor",
            result["safety_flags"],
        )

    def test_low_response_overrides_request_to_push_for_emotion(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她连续几轮只回嗯，没有主动延展，我想多推打出情绪",
            "--direction",
            "push",
        )
        self.assertEqual(result["state_route"]["id"], "low_response")
        self.assertIsNone(result["runtime_fields"]["tactical_direction"])
        self.assertEqual(result["runtime_fields"]["engagement_state"], "low")
        self.assertEqual(result["runtime_fields"]["direction_preference"], "none")

    def test_single_slow_reply_with_engagement_is_not_low_response(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她这次慢回，但仍然主动提问和延展",
        )
        self.assertNotEqual(result["state_route"]["id"], "low_response")
        self.assertEqual(result["runtime_fields"]["engagement_state"], "reciprocal")

    def test_continuous_slow_replies_with_engagement_are_not_low_response(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她连续慢回，但每次仍主动提问和延展",
        )
        self.assertNotEqual(result["state_route"]["id"], "low_response")
        self.assertEqual(result["runtime_fields"]["engagement_state"], "reciprocal")

    def test_flat_affect_or_drift_alone_does_not_authorize_action(self) -> None:
        flat = run_json(ROUTE_SCRIPT, "--text", "她没有情绪，怎么继续")
        self.assertEqual(flat["state_route"]["id"], "unknown_stage")
        self.assertEqual(flat["runtime_fields"]["affect_state"], "neutral")
        self.assertEqual(flat["runtime_fields"]["engagement_state"], "unknown")
        self.assertFalse(flat["runtime_fields"]["flat_but_engaged"])
        self.assertEqual(flat["runtime_fields"]["direction_preference"], "none")

        drift = run_json(
            ROUTE_SCRIPT,
            "--text",
            "已经聊成朋友了，怎么回到恋爱方向",
        )
        self.assertEqual(drift["state_route"]["id"], "unknown_stage")
        self.assertEqual(drift["runtime_fields"]["intent_alignment"], "drifted")
        self.assertEqual(
            drift["runtime_fields"]["romantic_reanchor_permitted"],
            "unknown",
        )
        self.assertNotIn(
            "romantic_intent_reanchor_without_fixed_turn_count",
            drift["safety_flags"],
        )

    def test_negated_evidence_markers_do_not_reverse_route(self) -> None:
        samples = (
            ("她并没有说只想做朋友，她明确想谈恋爱", "friend_only_boundary"),
            ("我不是只想做朋友，我是来找恋爱对象的", "friend_only_boundary"),
            ("她并非没有主动延展，而是一直主动提问", "low_response"),
            ("她不是没有情绪，她很兴奋而且主动提问", "neutral"),
        )
        for text, forbidden_value in samples:
            with self.subTest(text=text):
                result = run_json(ROUTE_SCRIPT, "--text", text)
                self.assertNotEqual(result["state_route"]["id"], "low_response")
                self.assertNotEqual(result["state_route"]["id"], "clarify")
                if forbidden_value == "friend_only_boundary":
                    self.assertNotEqual(
                        result["runtime_fields"]["intent_alignment"],
                        forbidden_value,
                    )
                elif forbidden_value == "neutral":
                    self.assertNotEqual(
                        result["runtime_fields"]["affect_state"],
                        forbidden_value,
                    )

    def test_planned_pull_is_feedback_gated(self) -> None:
        ready = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她继续接梗，还主动提问，看起来很舒服",
            "--previous-direction",
            "push",
            "--post-push-feedback",
            "positive",
        )
        self.assertEqual(ready["state_route"]["id"], "interest_push_pull")
        self.assertEqual(ready["runtime_fields"]["direction_preference"], "pull")
        self.assertEqual(ready["runtime_fields"]["planned_pull_status"], "ready")
        self.assertEqual(ready["runtime_fields"]["tactical_direction"], "pull")
        self.assertEqual(ready["runtime_fields"]["engagement_state"], "reciprocal")
        self.assertEqual(ready["runtime_fields"]["comfort_state"], "comfortable")

        blocked = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她的反馈变得含糊",
            "--previous-direction",
            "push",
            "--post-push-feedback",
            "negative",
            "--direction",
            "push",
        )
        self.assertEqual(blocked["runtime_fields"]["direction_preference"], "none")
        self.assertEqual(blocked["runtime_fields"]["planned_pull_status"], "blocked")
        self.assertIsNone(blocked["runtime_fields"]["tactical_direction"])

        incomplete_positive = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她的反馈看上去是正向的",
            "--previous-direction",
            "push",
            "--post-push-feedback",
            "positive",
        )
        self.assertEqual(
            incomplete_positive["runtime_fields"]["planned_pull_status"],
            "pending_feedback",
        )
        self.assertIsNone(
            incomplete_positive["runtime_fields"]["tactical_direction"]
        )

        pending = run_json(
            ROUTE_SCRIPT,
            "--text",
            "我刚发出上一条，还没有收到反馈",
            "--previous-direction",
            "push",
        )
        self.assertEqual(pending["state_route"]["id"], "interest_push_pull")
        self.assertEqual(pending["runtime_fields"]["direction_preference"], "none")
        self.assertEqual(
            pending["runtime_fields"]["planned_pull_status"],
            "pending_feedback",
        )

    def test_first_false_evaluation_starts_with_push_even_when_pull_requested(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "第一次假评她，我原本想先拉后推",
            "--direction",
            "pull",
            "--engagement",
            "reciprocal",
            "--comfort",
            "comfortable",
        )
        self.assertEqual(result["state_route"]["id"], "interest_push_pull")
        fields = result["runtime_fields"]
        self.assertEqual(fields["false_evaluation_stage"], "first")
        self.assertEqual(fields["direction_preference"], "push")
        self.assertEqual(fields["tactical_direction"], "push")
        self.assertEqual(fields["planned_pull_status"], "pending_feedback")
        self.assertEqual(
            fields["initial_false_evaluation_status"],
            "push_required",
        )
        self.assertEqual(
            fields["initial_false_evaluation_order"]["required_order"],
            "push_then_feedback_gated_pull",
        )
        self.assertIn(
            "first_false_evaluation_blocks_pull_first",
            result["safety_flags"],
        )

        awaiting = run_json(
            ROUTE_SCRIPT,
            "--text",
            "第一次假评她，我想先拉后推",
            "--direction",
            "pull",
            "--engagement",
            "reciprocal",
        )
        self.assertIsNone(awaiting["runtime_fields"]["tactical_direction"])
        self.assertEqual(
            awaiting["runtime_fields"]["planned_pull_status"],
            "not_applicable",
        )
        self.assertEqual(
            awaiting["runtime_fields"]["initial_false_evaluation_status"],
            "awaiting_eligibility",
        )

    def test_first_false_evaluation_does_not_override_exception_routes(self) -> None:
        samples = (
            ("她说不要再联系，我第一次假评要怎么做", "stop_boundary"),
            ("她有安全顾虑，我第一次假评要怎么做", "privacy_safety_age_consent"),
            ("我已经耗竭想回蓝，第一次假评要怎么做", "recovery"),
            ("她明确只想做朋友，我第一次假评要怎么做", "clarify"),
            ("她说最近很忙，我第一次假评要怎么做", "concern_condition"),
            ("她连续多轮低回应，没有主动延展，我第一次假评要怎么做", "low_response"),
            ("她主动约我见面，我第一次假评要怎么做", "invite"),
        )
        for text, expected_route in samples:
            with self.subTest(route=expected_route):
                result = run_json(
                    ROUTE_SCRIPT,
                    "--text",
                    text,
                    "--false-evaluation-stage",
                    "first",
                    "--direction",
                    "pull",
                    "--engagement",
                    "reciprocal",
                    "--comfort",
                    "comfortable",
                )
                self.assertEqual(result["state_route"]["id"], expected_route)
                self.assertIsNone(result["runtime_fields"]["tactical_direction"])
                self.assertEqual(
                    result["runtime_fields"]["planned_pull_status"],
                    "not_applicable",
                )
                self.assertEqual(
                    result["runtime_fields"]["initial_false_evaluation_status"],
                    "not_applicable",
                )

    def test_structured_discomfort_overrides_first_false_evaluation(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她反感，我第一次假评要先拉后推",
            "--false-evaluation-stage",
            "first",
            "--direction",
            "pull",
            "--engagement",
            "reciprocal",
            "--comfort",
            "uncomfortable",
        )
        self.assertEqual(result["state_route"]["id"], "stop_boundary")
        self.assertIsNone(result["runtime_fields"]["tactical_direction"])
        self.assertEqual(
            result["runtime_fields"]["initial_false_evaluation_status"],
            "not_applicable",
        )
        self.assertEqual(
            result["runtime_fields"]["phrase_retrieval"],
            "boundary_only",
        )

    def test_later_false_evaluation_keeps_normal_direction_selection(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "这不是第一次假评，当前适合拉",
            "--direction",
            "pull",
            "--engagement",
            "reciprocal",
            "--comfort",
            "comfortable",
        )
        self.assertEqual(result["state_route"]["id"], "interest_push_pull")
        fields = result["runtime_fields"]
        self.assertEqual(fields["false_evaluation_stage"], "later")
        self.assertEqual(fields["direction_preference"], "pull")
        self.assertEqual(fields["tactical_direction"], "pull")
        self.assertEqual(fields["planned_pull_status"], "not_applicable")
        self.assertEqual(
            fields["initial_false_evaluation_status"],
            "not_applicable",
        )

    def test_non_first_false_evaluation_states_do_not_force_push(self) -> None:
        expected_status = {
            "unknown": "unknown",
            "not_applicable": "not_applicable",
        }
        for false_evaluation_stage, initial_status in expected_status.items():
            with self.subTest(false_evaluation_stage=false_evaluation_stage):
                result = run_json(
                    ROUTE_SCRIPT,
                    "--text",
                    "当前适合拉",
                    "--state-route",
                    "interest_push_pull",
                    "--false-evaluation-stage",
                    false_evaluation_stage,
                    "--direction",
                    "pull",
                    "--engagement",
                    "reciprocal",
                    "--comfort",
                    "comfortable",
                )
                fields = result["runtime_fields"]
                self.assertEqual(fields["tactical_direction"], "pull")
                self.assertEqual(fields["direction_preference"], "pull")
                self.assertEqual(
                    fields["initial_false_evaluation_status"],
                    initial_status,
                )

    def test_first_false_evaluation_pull_remains_feedback_gated(self) -> None:
        ready = run_json(
            ROUTE_SCRIPT,
            "--text",
            "首个推之后她反馈积极，继续主动接梗而且互动舒服",
            "--false-evaluation-stage",
            "first",
            "--previous-direction",
            "push",
            "--post-push-feedback",
            "positive",
            "--engagement",
            "reciprocal",
            "--comfort",
            "comfortable",
        )
        self.assertEqual(ready["runtime_fields"]["tactical_direction"], "pull")
        self.assertEqual(ready["runtime_fields"]["planned_pull_status"], "ready")
        self.assertEqual(
            ready["runtime_fields"]["initial_false_evaluation_status"],
            "pull_ready",
        )

        blocked = run_json(
            ROUTE_SCRIPT,
            "--text",
            "首个推之后她反馈含糊",
            "--false-evaluation-stage",
            "first",
            "--previous-direction",
            "push",
            "--post-push-feedback",
            "ambiguous",
        )
        self.assertIsNone(blocked["runtime_fields"]["tactical_direction"])
        self.assertEqual(
            blocked["runtime_fields"]["planned_pull_status"],
            "blocked",
        )
        self.assertEqual(
            blocked["runtime_fields"]["initial_false_evaluation_status"],
            "blocked",
        )

        pending = run_json(
            ROUTE_SCRIPT,
            "--text",
            "首个推刚发出，还没有反馈",
            "--false-evaluation-stage",
            "first",
            "--previous-direction",
            "push",
        )
        self.assertIsNone(pending["runtime_fields"]["tactical_direction"])
        self.assertEqual(
            pending["runtime_fields"]["planned_pull_status"],
            "pending_feedback",
        )
        self.assertEqual(
            pending["runtime_fields"]["initial_false_evaluation_status"],
            "awaiting_feedback",
        )

    def test_post_push_higher_priority_states_override_planned_pull(self) -> None:
        discomfort = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她的反馈明显变差",
            "--previous-direction",
            "push",
            "--post-push-feedback",
            "discomfort",
            "--engagement",
            "reciprocal",
        )
        self.assertEqual(discomfort["state_route"]["id"], "stop_boundary")
        self.assertEqual(
            discomfort["runtime_fields"]["planned_pull_status"],
            "not_applicable",
        )
        self.assertEqual(
            discomfort["runtime_fields"]["phrase_retrieval"],
            "boundary_only",
        )

        low_response = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她持续减少回应",
            "--previous-direction",
            "push",
            "--post-push-feedback",
            "positive",
            "--engagement",
            "low",
        )
        self.assertEqual(low_response["state_route"]["id"], "low_response")
        self.assertEqual(
            low_response["runtime_fields"]["planned_pull_status"],
            "not_applicable",
        )

    def test_real_concern_does_not_become_counter_push(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她说最近很忙还有安全顾虑，不是开玩笑的推",
        )
        self.assertEqual(result["state_route"]["id"], "privacy_safety_age_consent")
        self.assertIsNone(result["state_route"]["push_pull_logic"])
        self.assertIsNone(result["runtime_fields"]["tactical_direction"])
        self.assertEqual(result["runtime_fields"]["push_back_eligible"], False)

    def test_accountability_routes_outside_push_pull(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "我刚才说错了，确实冒犯她，帮我道歉",
        )
        self.assertEqual(result["task_route"]["id"], "reply_request")
        self.assertEqual(result["state_route"]["id"], "clarify")
        self.assertEqual(result["primary_module"], "clarify")
        self.assertEqual(
            result["runtime_fields"]["tactical_action_constraints"],
            "not_applicable",
        )
        self.assertEqual(
            result["runtime_fields"]["exception_route"],
            "clarify",
        )

    def test_topic_stop_overrides_push_pull(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她说不想再聊这个话题，但推拉还要继续吗",
        )
        self.assertEqual(result["state_route"]["id"], "stop_boundary")
        self.assertEqual(result["runtime_fields"]["phrase_retrieval"], "boundary_only")
        self.assertFalse(result["runtime_fields"]["recontact_permitted"])

    def test_discomfort_or_topic_stop_overrides_push_pull(self) -> None:
        samples = (
            "她开始推我，但她明确说这让她不舒服",
            "她推完后说有点被冒犯",
            "她开始推我但说不要这样",
        )
        for text in samples:
            with self.subTest(text=text):
                result = run_json(ROUTE_SCRIPT, "--text", text)
                self.assertEqual(result["state_route"]["id"], "stop_boundary")
                self.assertEqual(result["runtime_fields"]["phrase_retrieval"], "boundary_only")
                self.assertEqual(result["runtime_fields"]["push_back_eligible"], False)

    def test_natural_counter_push_context_routes_to_interest(self) -> None:
        result = run_json(
            ROUTE_SCRIPT,
            "--text",
            "她推我后继续开玩笑和提问",
        )
        self.assertEqual(result["state_route"]["id"], "interest_push_pull")
        self.assertEqual(result["runtime_fields"]["push_back_eligible"], "unknown")
        self.assertEqual(result["runtime_fields"]["post_push_check"], "required")

    def test_intimacy_requires_all_context_flags(self) -> None:
        blocked = run_json(
            PHRASE_SCRIPT,
            "--route",
            "intimacy_conditional",
            "--query",
            "暧昧",
            "--explicit-same-topic",
            "--age-identity-basis",
            "--mutual-feedback",
        )
        self.assertEqual(blocked["retrieval_status"], "blocked_until_context_verified")
        self.assertEqual(blocked["matches"], [])

        allowed = run_json(
            PHRASE_SCRIPT,
            "--route",
            "intimacy_conditional",
            "--query",
            "暧昧",
            "--explicit-same-topic",
            "--age-identity-basis",
            "--mutual-feedback",
            "--no-refusal-or-discomfort",
        )
        self.assertEqual(
            allowed["retrieval_status"],
            "candidate_reference_after_context_review",
        )
        self.assertTrue(allowed["matches"])

        shortcut = run_json(
            PHRASE_SCRIPT,
            "--route",
            "intimacy_conditional",
            "--query",
            "暧昧",
            "--sexual-context",
        )
        self.assertEqual(shortcut["retrieval_status"], "blocked_until_context_verified")

    def test_full_index_is_source_only_audit(self) -> None:
        result = run_json(
            PHRASE_SCRIPT,
            "--route",
            "teasing_push_pull",
            "--query",
            "调侃",
            "--full-index",
        )
        self.assertEqual(
            result["retrieval_status"],
            "candidate_reference_with_source_audit",
        )
        self.assertEqual(
            result["source"],
            "candidate_index_plus_full_index_source_only_audit",
        )
        self.assertEqual(result["sendability"], "not_granted")
        self.assertTrue(any("source-only" in warning for warning in result["warnings"]))

    def test_all_shards_and_counts_are_consistent(self) -> None:
        phrase_index = json.loads(
            (BUNDLE / "runtime" / "phrase-route-index.json").read_text(encoding="utf-8")
        )
        for route in phrase_index["routes"]:
            with self.subTest(route=route["id"]):
                shard = BUNDLE / route["shard"]
                self.assertTrue(shard.is_file())
                document = json.loads(shard.read_text(encoding="utf-8"))
                self.assertEqual(document["route"], route["id"])
                self.assertIsInstance(document["entries"], list)

        units = json.loads(
            (BUNDLE / "runtime" / "unit-index.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            (units["unit_count"], units["canonical_count"], units["candidate_count"]),
            (49, 2, 47),
        )

    def test_generated_routes_match_bundled_configuration(self) -> None:
        config = json.loads(ROUTE_CONFIG.read_text(encoding="utf-8"))
        runtime = json.loads(ROUTE_INDEX.read_text(encoding="utf-8"))
        self.assertEqual(runtime["stage_navigation"], config["stage_navigation"])
        self.assertEqual(
            runtime["stage_navigation"]["evidence_layers"],
            ["observed", "reported", "inferred"],
        )
        configured_states = {
            route["id"]: route for route in config["state_routes"]
        }
        runtime_states = {
            route["id"]: route for route in runtime["state_routes"]
        }
        for route_id in ("low_response", "interest_push_pull"):
            self.assertEqual(
                runtime_states[route_id]["match_any"],
                configured_states[route_id]["match_any"],
            )
        self.assertEqual(
            runtime_states["interest_push_pull"]["push_pull_logic"],
            configured_states["interest_push_pull"]["push_pull_logic"],
        )
        entry = RUNTIME_ENTRY.read_text(encoding="utf-8")
        self.assertIn("flat_but_engaged", entry)
        self.assertIn("不按固定回合数", entry)
        self.assertIn("不设固定比例", entry)
        self.assertIn("首次假评", entry)
        self.assertIn("push_then_feedback_gated_pull", entry)

    def test_example_gate_stays_closed_until_stage_and_direction_are_clear(self) -> None:
        no_context = run_json(
            ROUTE_SCRIPT,
            "--text",
            "直接帮我回复",
            "--task-route",
            "reply_request",
        )
        self.assertFalse(no_context["example_gate"]["allowed"])
        self.assertFalse(no_context["example_gate"]["stage_clear"])
        self.assertFalse(no_context["example_gate"]["direction_clear"])

        no_direction = run_json(
            ROUTE_SCRIPT,
            "--text",
            "直接帮我回复，当前在兴趣证据收集阶段",
            "--task-route",
            "reply_request",
            "--state-route",
            "interest_push_pull",
            "--engagement",
            "reciprocal",
            "--comfort",
            "comfortable",
        )
        self.assertFalse(no_direction["example_gate"]["allowed"])
        self.assertTrue(no_direction["example_gate"]["stage_clear"])
        self.assertFalse(no_direction["example_gate"]["direction_clear"])


if __name__ == "__main__":
    unittest.main()
