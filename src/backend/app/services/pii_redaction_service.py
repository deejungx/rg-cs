import logging
from threading import Lock

from app.core.config import settings
from src.shared.schemas import DocumentParseResult

logger = logging.getLogger(__name__)


class _BlankNlpEngine:
    def __init__(self, language: str) -> None:
        self.language = language
        self._nlp = None

    def load(self) -> None:
        import spacy

        self._nlp = spacy.blank(self.language)

    def is_loaded(self) -> bool:
        return self._nlp is not None

    def process_text(self, text: str, language: str):
        from presidio_analyzer.nlp_engine import NlpArtifacts

        if self._nlp is None:
            raise ValueError("NLP engine is not loaded.")

        doc = self._nlp(text)
        tokens_indices = [token.idx for token in doc]
        lemmas = [token.lemma_ if token.lemma_ else token.text for token in doc]
        return NlpArtifacts([], doc, tokens_indices, lemmas, self, language)

    def process_batch(
        self,
        texts,
        language: str,
        batch_size: int = 1,
        n_process: int = 1,
        **kwargs,
    ):
        for text in texts:
            yield text, self.process_text(text, language)

    def is_stopword(self, word: str, language: str) -> bool:
        return bool(self._nlp and self._nlp.vocab[word].is_stop)

    def is_punct(self, word: str, language: str) -> bool:
        return bool(self._nlp and self._nlp.vocab[word].is_punct)

    def get_supported_entities(self) -> list[str]:
        return []

    def get_supported_languages(self) -> list[str]:
        return [self.language]


class PiiRedactionService:
    def __init__(
        self,
        *,
        enabled: bool,
        language: str,
        entities: list[str],
    ) -> None:
        self.enabled = enabled
        self.language = language
        self.entities = [entity for entity in entities if entity]
        self._lock = Lock()
        self._initialized = False
        self._available = False
        self._analyzer = None
        self._anonymizer = None

    def redact_text(self, text: str) -> str:
        if not self.enabled or not text.strip():
            return text
        if not self._ensure_initialized():
            return text

        results = self._analyzer.analyze(
            text=text,
            language=self.language,
            entities=self.entities or None,
        )
        if not results:
            return text
        return self._anonymizer.anonymize(text=text, analyzer_results=results).text

    def redact_parse_result(self, parsed: DocumentParseResult) -> DocumentParseResult:
        source_text = parsed.source_text
        if not source_text:
            return parsed
        redacted_text = self.redact_text(source_text)
        parsed.text = redacted_text
        parsed.redaction_applied = redacted_text != source_text
        return parsed

    def _ensure_initialized(self) -> bool:
        if self._initialized:
            return self._available

        with self._lock:
            if self._initialized:
                return self._available

            self._initialized = True
            try:
                from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
                from presidio_analyzer import RecognizerRegistry
                from presidio_anonymizer import AnonymizerEngine

                registry = RecognizerRegistry(supported_languages=[self.language])
                registry.add_recognizer(
                    PatternRecognizer(
                        supported_entity="EMAIL_ADDRESS",
                        supported_language=self.language,
                        patterns=[
                            Pattern(
                                name="email",
                                regex=r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b",
                                score=0.95,
                            )
                        ],
                    )
                )
                registry.add_recognizer(
                    PatternRecognizer(
                        supported_entity="PHONE_NUMBER",
                        supported_language=self.language,
                        patterns=[
                            Pattern(
                                name="phone",
                                regex=r"(?:(?<=\s)|^)(?:\+?\d[\d()\-\s]{7,}\d)(?=\s|$)",
                                score=0.8,
                            )
                        ],
                    )
                )
                registry.add_recognizer(
                    PatternRecognizer(
                        supported_entity="URL",
                        supported_language=self.language,
                        patterns=[
                            Pattern(
                                name="url",
                                regex=r"\b(?:https?://|www\.)\S+\b",
                                score=0.85,
                            )
                        ],
                    )
                )
                self._analyzer = AnalyzerEngine(
                    registry=registry,
                    nlp_engine=_BlankNlpEngine(self.language),
                    supported_languages=[self.language],
                )
                self._anonymizer = AnonymizerEngine()
                self._available = True
            except Exception:
                logger.warning(
                    "Presidio PII redaction could not be initialized; continuing without text redaction.",
                    exc_info=True,
                )

        return self._available


pii_redaction_service = PiiRedactionService(
    enabled=settings.pii_redaction_enabled,
    language=settings.pii_redaction_language,
    entities=[
        entity.strip()
        for entity in settings.pii_redaction_entities.split(",")
        if entity.strip()
    ],
)
