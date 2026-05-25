-- Top jobs by candidate volume
SELECT job_id, COUNT(*) AS candidate_count
FROM candidate_job_matches
GROUP BY job_id
ORDER BY candidate_count DESC;

-- Average interview score by job
SELECT i.job_id, AVG(s.total_score) AS avg_interview_score
FROM answer_scores s
JOIN interview_answers a ON a.id = s.answer_id
JOIN interviews i ON i.id = a.interview_id
GROUP BY i.job_id
ORDER BY avg_interview_score DESC;

-- Top missing skills by job
SELECT job_id, json_each.value AS missing_skill, COUNT(*) AS misses
FROM candidate_job_matches, json_each(candidate_job_matches.missing_required_skills)
GROUP BY job_id, missing_skill
ORDER BY misses DESC;

-- Candidate funnel conversion
SELECT status, COUNT(*) AS total
FROM candidates
GROUP BY status;

-- Recruiter override rate
SELECT override_ai_recommendation, COUNT(*) AS total
FROM recruiter_decisions
GROUP BY override_ai_recommendation;

-- Human review percentage
SELECT
  SUM(CASE WHEN human_review_required THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS human_review_pct
FROM interview_reports;

