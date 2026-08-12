# Fixed detector reliability benchmarks

DefeatWatermarker evaluates false positives and false negatives with **fixed labelled corpora**. The benchmark runner does not alter detector thresholds, search for evasive examples, or mutate examples in response to detector scores.

Each corpus pins one adapter ID and a bounded set of labelled artifact files. A run records, per case, only the case ID, artifact SHA-256/length, expected label, observed label, confidence and verification state. It does not serialize the artifact bytes.

Reported aggregate metrics include true/false positives and negatives, accuracy, precision, recall, specificity, false-positive rate and false-negative rate. Undefined rates are represented as `null` rather than silently coerced to zero.

Corpus paths must be normalized relative paths that resolve inside the corpus directory. Individual artifacts and the total corpus are byte-bounded.

The bundled `builtin-container-hints-smoke` corpus is intentionally tiny and exists to exercise the benchmark contract; it is not statistically meaningful evidence about real-world detector reliability. Provider/standards adapters need appropriately sourced, independently reviewed positive and negative corpora before reliability claims should be made.
