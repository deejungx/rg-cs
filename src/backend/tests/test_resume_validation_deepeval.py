import os

import pytest

pytest.importorskip("deepeval")

from deepeval import assert_test
from deepeval.dataset import Golden
from src.ai.evals.resume_validation import (
    resume_validation_dataset,
    resume_validation_metrics,
    run_resume_validation_eval,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DEEPEVAL_EVALS") != "1" or not os.getenv("OPENAI_API_KEY"),
    reason="Enable RUN_DEEPEVAL_EVALS=1 and OPENAI_API_KEY to run DeepEval resume validation checks.",
)

@pytest.mark.parametrize("golden", resume_validation_dataset.goldens)
def test_resume_validation_trace(golden: Golden) -> None:
    run_resume_validation_eval(golden.input)
    assert_test(golden=golden, metrics=resume_validation_metrics)
