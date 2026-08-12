# Interoperability matrix runner

The interoperability runner compares multiple read-only detector adapters over the same fixed artifact set. It records artifact hashes/lengths, each adapter's supported/detected/confidence/family/verification-state result, and pairwise detection agreement.

It is deliberately an **agreement measurement**, not a compliance conclusion. Two detectors can agree and both be wrong; reliability against labelled corpora is measured separately. Likewise, a framework capable of running matrices does not prove that any particular marking technology is interoperable across providers or standards.

Matrix definitions are strict, content-addressed, path-contained and byte-bounded. Reports contain no artifact bytes.

The framework capability is `interoperability.matrix-runner.v1`. The stronger Article 50 profile requirement `interoperability.matrix.v1` remains unavailable until the repository contains representative matrices using independent implementations and reviewed fixtures.
