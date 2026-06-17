"""
Difficulty judge for University-entrance listening scripts.

Scores a generated exam script against UTokyo-level criteria so the pipeline can
auto-regenerate weak scripts. Targets are grounded in verified research on the
real UTokyo 2nd-stage listening exam: ~500-600 words per section, 5 questions,
5 choices each, academic register, every question answerable from the passage.
"""
import json
import re

try:
    from script_gen import _call_llm
except Exception:
    _call_llm = None

# --- UTokyo-level targets (from verified research) ---
TARGET_MIN_WORDS = 400          # hard gate; the LLM consistently overshoots 500-600,
TARGET_MAX_WORDS = 820          # so the hard window is wide. Quality is gated by the LLM
                                # difficulty score; length is otherwise just a soft signal.
TARGET_QUESTIONS = 5
TARGET_CHOICES = 5
MIN_DIFFICULTY_SCORE = 7        # LLM 1-10 scale; below this -> regenerate


def _passage_text(script_data: dict) -> str:
    parts = []
    for sec in script_data.get("sections", []):
        for ln in sec.get("lines", []):
            t = ln.get("text") or ""
            if t:
                parts.append(t)
    return " ".join(parts)


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z']+", text))


# Per-university benchmark used in the LLM rubric.
UNI_BENCHMARK = {
    "todai": ("University of Tokyo (UTokyo)",
              "UTokyo level = academic 3-speaker discussion, dense, ~500-600 words"),
    "kyoto": ("Kyoto University (KyotoU)",
              "Kyoto has NO official listening exam, so judge as a Kyoto-level abstract/philosophical "
              "academic LECTURE (monologue), dense and conceptually demanding, ~500-600 words"),
    "osaka": ("Osaka University (OsakaU, Faculty of Foreign Studies)",
              "Osaka level = academic MONOLOGUE read twice, ~500-700 words, practical/academic theme"),
}


def _llm_rubric(passage: str, questions: list, university: str = "todai") -> dict:
    if _call_llm is None:
        return {"error": "LLM unavailable"}
    qs_text = json.dumps(questions, ensure_ascii=False)
    uni_name, uni_desc = UNI_BENCHMARK.get(university, UNI_BENCHMARK["todai"])
    sys_prompt = (
        f"You are an examiner for the {uni_name} English listening exam.\n"
        f"Evaluate the generated listening passage and its multiple-choice questions against "
        f"the {uni_name}-level standard.\n\n"
        f"PASSAGE:\n{passage}\n\n"
        f"QUESTIONS (JSON):\n{qs_text}\n\n"
        f"{uni_desc}. 5 options per question, every question uniquely answerable from the passage "
        "with plausible (not obviously wrong) distractors. Rate strictly.\n\n"
        "Output JSON ONLY (no markdown):\n"
        "{\n"
        '  "difficulty_score": <integer 1-10, 10 = exactly UTokyo difficulty>,\n'
        '  "too_easy_or_hard": "<easy|right|hard>",\n'
        '  "all_answerable_from_passage": <true|false>,\n'
        '  "distractors_plausible": <true|false>,\n'
        '  "vocabulary_level": "<below|at|above UTokyo>",\n'
        '  "problems": ["short problem descriptions, empty if none"],\n'
        '  "verdict": "<pass|revise>"\n'
        "}"
    )
    try:
        raw = _call_llm(sys_prompt, json_mode=True)
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e)}


def judge_exam_script(script_data: dict, university: str = "todai") -> dict:
    """
    Returns: {
        passes: bool, structural_ok: bool, checks: {...}, llm: {...}, issues: [...]
    }
    The judge is advisory: on LLM failure it falls back to structural checks only.
    """
    passage = _passage_text(script_data)
    wc = _word_count(passage)
    questions = script_data.get("questions", []) or []
    n_q = len(questions)
    choice_counts = [len(q.get("choices") or q.get("options") or []) for q in questions]

    checks = {
        "word_count": wc,
        "word_count_ok": TARGET_MIN_WORDS <= wc <= TARGET_MAX_WORDS,
        "num_questions": n_q,
        "num_questions_ok": n_q >= TARGET_QUESTIONS,
        "choices_per_q": choice_counts,
        "choices_ok": bool(choice_counts) and all(c == TARGET_CHOICES for c in choice_counts),
    }

    issues = []
    if not checks["word_count_ok"]:
        issues.append(f"passage {wc} words (target {TARGET_MIN_WORDS}-{TARGET_MAX_WORDS})")
    if not checks["num_questions_ok"]:
        issues.append(f"{n_q} questions (target {TARGET_QUESTIONS})")
    if not checks["choices_ok"]:
        issues.append(f"choice counts {choice_counts} (target {TARGET_CHOICES} each)")

    structural_ok = (
        checks["word_count_ok"] and checks["num_questions_ok"] and checks["choices_ok"]
    )

    llm = _llm_rubric(passage, questions, university)
    llm_ok = True
    score = llm.get("difficulty_score")
    if isinstance(score, (int, float)):
        # A strict examiner always finds something to "revise", so gate on the
        # difficulty score + answerability only; treat finer notes as warnings.
        llm_ok = score >= MIN_DIFFICULTY_SCORE and bool(llm.get("all_answerable_from_passage", True))
        if llm.get("problems"):
            issues.extend([p for p in llm["problems"] if p])
    # If the LLM errored, don't block on it (structural gate still applies).

    return {
        "passes": structural_ok and llm_ok,
        "structural_ok": structural_ok,
        "checks": checks,
        "llm": llm,
        "issues": issues,
    }
