# Responsible AI Hiring

## Core stance

HireOS AI is decision support software, not an automated hiring decision-maker.

## Product limitations

- Resume parsing and answer scoring are probabilistic.
- Semantic interpretation can miss nuance, especially when answers are concise or domain-specific.
- Local heuristic mode is demo-ready but not a substitute for calibrated production evaluation.

## Fairness considerations

- Protected attributes should not be used in scoring or ranking.
- Recruiters must be able to see why a score was produced.
- Low-confidence outputs should increase review pressure, not silently downgrade candidates.

## Human-in-the-loop design

- AI output is presented as recommendation, not final decision.
- Reports explicitly show `human_review_required`.
- Recruiters can override AI recommendations and record notes.
- Hiring managers and admins can review downstream outcomes.

## Auditability

- Audit logs capture entity changes and recruiter decisions.
- Event envelopes keep the lifecycle observable.
- Reports preserve score explanations and next-step rationale.

## Data retention suggestions

- Retain raw resumes only as long as needed for the hiring workflow.
- Separate model evaluation artifacts from personal candidate data when possible.
- Apply deletion policies for archived candidates and inactive companies.

## Privacy considerations

- Resume uploads and transcripts contain personal data.
- Production deployments should add encryption, retention rules, access review, and DSR handling.

