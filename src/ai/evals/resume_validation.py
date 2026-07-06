"""DeepEval harness for resume validation CrewAI runs."""

from deepeval.dataset import EvaluationDataset, Golden
from deepeval.metrics import TaskCompletionMetric
from deepeval.tracing import observe

from src.ai.crews.cv_extraction_crew import CvExtractionCrew
from src.ai.prompts.cv_extraction import RESUME_VALIDATION_PROMPT

resume_validation_dataset = EvaluationDataset(
    goldens=[
        Golden(
            input=(
                "Jane Doe\njane.doe@example.com\nExperience\nSenior Software Engineer at Example Corp\n"
                "Education\nBS Computer Science\nSkills\nPython, FastAPI, Redis"
            ),
            expected_output=(
                "The result should identify the document as a resume or CV with a short evidence-based reason."
            ),
        ),
        Golden(
            input=(
                "Weekly grocery list\nMilk\nEggs\nBread\n"
                "Notes: remember to buy detergent and paper towels."
            ),
            expected_output=(
                "The result should identify the document as not being a resume or CV with a short evidence-based reason."
            ),
        ),
    ]
)

resume_validation_metrics = [TaskCompletionMetric()]


@observe(name="cv_resume_validation")
def run_resume_validation_eval(document_text: str) -> str:
    """Run the existing resume-validation crew under a DeepEval root span."""

    result = CvExtractionCrew().validate_resume(
        RESUME_VALIDATION_PROMPT.format(document_text=document_text)
    )
    return result.model_dump_json()
