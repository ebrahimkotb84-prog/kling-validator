from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from collections import OrderedDict

EXPECTED_SHA256 = "b94f9ad3f37ba8740477cf8337343f5b9f55d66e832b0c893a6ada6b0de1d639"


def _split(text: str):
    marker = "### Negative Prompt"
    if marker in text:
        positive, negative = text.split(marker, 1)
        return positive, negative
    marker = "Negative Prompt"
    if marker in text:
        positive, negative = text.split(marker, 1)
        return positive, negative
    return text, ""


def _ordered(text: str, phrases: list[str]) -> bool:
    pos = -1
    for phrase in phrases:
        nxt = text.find(phrase, pos + 1)
        if nxt < 0:
            return False
        pos = nxt
    return True


def validate_details(text: str) -> OrderedDict[str, dict]:
    positive, negative = _split(text)
    details: OrderedDict[str, dict] = OrderedDict()

    # T01 Template Structure
    t01_phrases = [
        "Use **Reference Image 01** as the exact starting frame and **Reference Image 02** as the exact ending frame.",
        "Preserve the Princess's identity",
        "The reference images define the absolute visual boundaries of this shot.",
        "The camera follows only the framing transition defined by the two reference images.",
        "Begin exactly from **Reference Image 01**.",
        "The royal procession is already moving naturally forward from the first frame.",
        "The Princess's hair, costume, embroidered cloak, sleeves, jewelry, and body respond only with subtle natural secondary motion",
        "The movement ends immediately upon reaching the exact Princess position",
        "The final frame must be visually identical to **Reference Image 02**",
        "### Negative Prompt",
    ]
    ok = _ordered(text, t01_phrases)
    details["T01"] = {"pass": ok, "reason": "locked SHOT03 function order present" if ok else "required SHOT03 function order/opening/negative block missing or displaced"}

    # T02 Source Attribution: deterministic rejection of known unsupported insertions.
    unsupported_source_tokens = [
        "white doves", "fireworks", "confetti", "new statue", "extra fountain",
        "unseen balcony", "new carriage", "new soldiers",
    ]
    found = [t for t in unsupported_source_tokens if t.lower() in positive.lower()]
    ok = not found
    details["T02"] = {"pass": ok, "reason": "no known unsourced inserted content" if ok else f"unsupported positive content: {found}"}

    # T03 Starting State
    required_start = [
        "Begin exactly from **Reference Image 01**.",
        "already moving naturally forward from the first frame",
        "crowds on both sides are already naturally active and joyful from the first frame",
        "fountain remains continuously active throughout the entire shot",
        "water flows clearly and naturally",
        "Princess responds to the people's affection with a soft, calm, warm smile",
    ]
    forbidden_start = ["initially still", "starts moving after the first frame", "begins moving after the first frame", "waits before moving"]
    ok = all(p.lower() in positive.lower() for p in required_start) and not any(p in positive.lower() for p in forbidden_start)
    details["T03"] = {"pass": ok, "reason": "S0 continuous start state is explicit" if ok else "S0 is delayed, initially still, or missing required continuous start facts"}

    # T04 Causal Predecessors
    forbidden_predecessors = [
        "after the procession has fully settled", "after procession fully settled",
        "after the horse stops completely", "after the crowd finishes greeting",
    ]
    ok = not any(p in positive.lower() for p in forbidden_predecessors)
    details["T04"] = {"pass": ok, "reason": "no impossible or invented completed predecessor" if ok else "invented/impossible predecessor detected"}

    # T05 Secondary Motion
    secondary_required = [
        "respond only with subtle natural secondary motion caused by the movement of the horse and her own body",
        "realistic gravity, weight, folds, inertia",
        "hair moves with natural weight and subtle inertia only",
        "jewelry responds with minimal physically believable movement",
        "movement ends immediately upon reaching",
    ]
    autonomous = ["move freely on their own", "moves freely on its own", "independent autonomous motion", "without dependency on the horse"]
    ok = all(p.lower() in positive.lower() for p in secondary_required) and not any(p in positive.lower() for p in autonomous)
    details["T05"] = {"pass": ok, "reason": "secondary motions have physical dependency/behavior/end stop" if ok else "secondary motion dependency/physics/settle-stop missing or autonomous"}

    # T06 Only-After Discipline
    invented_gate = ["only after", "only-after"]
    ok = not any(p in positive.lower() for p in invented_gate)
    details["T06"] = {"pass": ok, "reason": "no unauthorized Only-After gate" if ok else "unauthorized Only-After serialization detected"}

    # T07 Negative Reflection
    negative_required = [
        "Do not change the Princess's identity",
        "Do not expand the environment.",
        "No camera pan, tilt, zoom",
        "No anatomy errors",
        "No hand deformation",
        "No horse anatomy deformation",
        "No unrealistic water physics",
        "Do not continue the procession",
        "The shot must end immediately at **Reference Image 02**.",
    ]
    ok = all(p.lower() in negative.lower() for p in negative_required)
    details["T07"] = {"pass": ok, "reason": "negative prompt mirrors critical positive constraints" if ok else "critical negative reflection missing"}

    # T08 Visual Boundaries
    boundary_required = [
        "absolute visual boundaries",
        "never reveal, generate, infer, reconstruct, or explore anything outside",
        "strictly limited to the necessary transition",
        "At no point may it expand the environment",
    ]
    forbidden_reveal = [
        "pan upward to reveal", "zoom out to reveal", "reveal additional towers", "reveal unseen sky",
        "explore the square beyond", "show areas outside the references",
    ]
    ok = all(p.lower() in positive.lower() for p in boundary_required) and not any(p in positive.lower() for p in forbidden_reveal)
    details["T08"] = {"pass": ok, "reason": "reference frames remain absolute visual boundary" if ok else "environment expansion or unauthorized reveal detected"}

    # T09 Contradictions
    contradiction_tokens = [
        "camera remains completely locked", "camera is completely locked", "no camera movement at all",
        "the procession remains completely still", "horse must both move and remain still",
    ]
    ok = not any(p in positive.lower() for p in contradiction_tokens)
    details["T09"] = {"pass": ok, "reason": "no direct functional contradiction detected" if ok else "contradictory camera/motion instruction detected"}

    # T10 Exact End Lock
    end_required = [
        "The movement ends immediately upon reaching",
        "The final frame must be visually identical to **Reference Image 02**",
        "Do not continue the procession, horse movement, camera movement, Princess movement, gaze movement, crowd development, or any other progression beyond the exact state shown in **Reference Image 02**.",
        "The shot must end immediately at **Reference Image 02**.",
        "No final frame different from **Reference Image 02**.",
    ]
    forbidden_after_end = [
        "after reference image 02, continue", "after reaching reference image 02, continue",
        "continue beyond reference image 02", "then continue walking after the final frame",
    ]
    ok = all(p.lower() in text.lower() for p in end_required) and not any(p in positive.lower() for p in forbidden_after_end)
    details["T10"] = {"pass": ok, "reason": "all progression is locked to stop at Reference Image 02" if ok else "exact end lock missing/weakened or progression continues after end"}

    # T11 Reference Discipline
    reference_required = [
        "exact starting frame", "exact ending frame", "absolute visual boundaries",
        "final frame must be visually identical to **Reference Image 02**",
    ]
    unsupported_effects = [
        "rose petals", "cinematic lens flare", "new decorative banners", "sparkles",
        "magical glow", "dramatic fog", "extra architecture",
    ]
    ok = all(p.lower() in text.lower() for p in reference_required) and not any(p in positive.lower() for p in unsupported_effects)
    details["T11"] = {"pass": ok, "reason": "references remain governing constraints with no unsupported positive additions" if ok else "reference discipline violated by unsupported addition or weakened authority"}

    return details


def validate(text: str) -> OrderedDict[str, bool]:
    return OrderedDict((k, v["pass"]) for k, v in validate_details(text).items())


def generate_mutations(base: str) -> OrderedDict[str, str]:
    muts: OrderedDict[str, str] = OrderedDict()

    muts["T01"] = base.replace(
        "Use **Reference Image 01** as the exact starting frame and **Reference Image 02** as the exact ending frame.\n\n",
        "",
        1,
    )

    muts["T02"] = base.replace(
        "Begin exactly from **Reference Image 01**.",
        "Begin exactly from **Reference Image 01**. White doves circle overhead as a ceremonial flourish.",
        1,
    )

    muts["T03"] = base.replace(
        "The royal procession is already moving naturally forward from the first frame.",
        "The royal procession is initially still and begins moving after the first frame.",
        1,
    )

    muts["T04"] = base.replace(
        "The white horse continues walking forward at a calm, dignified, physically natural pace",
        "After the procession has fully settled, the white horse continues walking forward at a calm, dignified, physically natural pace",
        1,
    )

    muts["T05"] = base.replace(
        "The Princess's hair, costume, embroidered cloak, sleeves, jewelry, and body respond only with subtle natural secondary motion caused by the movement of the horse and her own body.",
        "The Princess's hair, costume, embroidered cloak, sleeves, jewelry, and body move freely on their own without dependency on the horse.",
        1,
    )

    muts["T06"] = base.replace(
        "The fountain remains continuously active throughout the entire shot.",
        "Only After the procession reaches the center of the square, the fountain becomes active throughout the rest of the shot.",
        1,
    )

    camera_negative = "No camera pan, tilt, zoom, dolly, orbit, crane, handheld movement, lateral exploration, vertical exploration, reframing, or any other camera behavior beyond the exact framing transition required to move from **Reference Image 01** to **Reference Image 02**.\n\n"
    muts["T07"] = base.replace(camera_negative, "", 1)

    muts["T08"] = base.replace(
        "The camera follows only the framing transition defined by **Reference Image 01** and **Reference Image 02**.",
        "The camera follows only the framing transition defined by **Reference Image 01** and **Reference Image 02**. It may also pan upward to reveal additional towers and unseen sky beyond the references.",
        1,
    )

    muts["T09"] = base.replace(
        "The camera follows only the framing transition defined by the two reference images.",
        "The camera remains completely locked with no camera movement at all. The camera follows only the framing transition defined by the two reference images.",
        1,
    )

    muts["T10"] = base.replace(
        "The movement ends immediately upon reaching the exact Princess position",
        "After Reference Image 02, continue the procession and camera movement briefly. The movement ends immediately upon reaching the exact Princess position",
        1,
    )

    muts["T11"] = base.replace(
        "Begin exactly from **Reference Image 01**.",
        "Begin exactly from **Reference Image 01**. Add rose petals, cinematic lens flare, and new decorative banners for extra beauty.",
        1,
    )

    return muts


def run_audit(candidate_path: pathlib.Path, output_path: pathlib.Path | None = None) -> int:
    data = candidate_path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    text = data.decode("utf-8")
    baseline = validate_details(text)
    mutations = generate_mutations(text)
    mutation_results = OrderedDict()
    mutation_suite_valid = True

    for test_id, mutated in mutations.items():
        results = validate_details(mutated)
        designated_failed = not results[test_id]["pass"]
        unrelated_pass_count = sum(1 for k, v in results.items() if k != test_id and v["pass"])
        valid = designated_failed and unrelated_pass_count > 0
        mutation_suite_valid = mutation_suite_valid and valid
        mutation_results[test_id] = {
            "designated_test_failed": designated_failed,
            "unrelated_tests_passing": unrelated_pass_count,
            "valid_mutation_check": valid,
            "designated_reason": results[test_id]["reason"],
        }

    all_baseline_pass = all(item["pass"] for item in baseline.values())
    sha_match = sha == EXPECTED_SHA256
    overall = "VALIDATED-PASS" if sha_match and all_baseline_pass and mutation_suite_valid else "VALIDATED-FAIL"

    report = OrderedDict([
        ("candidate_sha256", sha),
        ("expected_sha256", EXPECTED_SHA256),
        ("sha_match", sha_match),
        ("baseline", baseline),
        ("mutations", mutation_results),
        ("mutation_suite_valid", mutation_suite_valid),
        ("overall", overall),
        ("scope_note", "Deterministic structural/source/sequence/negative/boundary/end-lock audit. This does not guarantee Kling's rendered visual quality."),
    ])

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if output_path:
        output_path.write_text(rendered + "\n", encoding="utf-8")
    return 0 if overall == "VALIDATED-PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", default="candidate_baseline.txt")
    parser.add_argument("--output", default="audit_report.json")
    args = parser.parse_args()
    return run_audit(pathlib.Path(args.candidate), pathlib.Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
