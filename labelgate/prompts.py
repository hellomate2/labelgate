"""Prompts. ZERO_SHOT_* are copied verbatim from zero_shot() in ncbi-nlp/MedCalc-Bench
evaluation/run.py (commit 20b10f9, lines 16 to 19)."""
import json

ZERO_SHOT_SYSTEM = 'You are a helpful assistant for calculating a score for a given patient note. Please think step-by-step to solve the question and then generate the required score. Your output should only contain a JSON dict formatted as {"step_by_step_thinking": str(your_step_by_step_thinking_procress_to_solve_the_question), "answer": str(short_and_direct_answer_of_the_question)}.'


def zero_shot_user(note, question):
    return f'Here is the patient note:\n{note}\n\nHere is the task:\n{question}\n\nPlease directly output the JSON dict formatted as {{"step_by_step_thinking": str(your_step_by_step_thinking_procress_to_solve_the_question), "answer": str(short_and_direct_answer_of_the_question)}}:'


EXTRACT_SYSTEM = "You copy values out of clinical notes. You never compute, convert or guess. Output only JSON."


def extract_user(note, names):
    schema = {name: {"value": "number or null", "unit": "string or null", "span": "exact text copied from the note"} for name in names}
    return (
        "Here is a patient note:\n" + note + "\n\n"
        "For each input below, find the value in the note that a careful reader would use for it, "
        "as it was when the patient was first admitted. Give the number exactly as the note writes it, "
        "the unit the note prints next to it, and the shortest span of the note that contains both, copied "
        "character for character. If the note does not state the input, use null.\n\n"
        "Inputs: " + ", ".join(names) + "\n\n"
        "Output one JSON object with this shape and nothing else:\n" + json.dumps(schema, ensure_ascii=False)
    )
