# Tuning Log — RAG Retrieval Variants
## 1. Objective
Evaluate three retrieval-time tuning variants against the dense baseline using the Sprint 4 scorecard: Faithfulness, Answer Relevance, Context Recall, and Completeness.
## 2. Evaluation setup
- Baseline: dense retrieval, `top_k_search=10`, `top_k_select=3`, no rerank.
- Variant 1: hybrid retrieval, `top_k_search=10`, `top_k_select=3`, no rerank.
- Variant 2: dense + rerank, `top_k_search=10`, `top_k_select=3`, `use_rerank=True`.
- Variant 3: dense + query expansion, `top_k_search=20`, `top_k_select=3`, no rerank, `query_transform_strategy='expansion'`.
- Dataset size: 10 evaluation questions (`gq01`–`gq10`).
- Scoring pipeline: `score_faithfulness`, `score_answer_relevance`, `score_context_recall`, `score_completeness` in `eval.py`.

## 3. Aggregate results
| Config | Faithfulness | Relevance | Context Recall | Completeness | Overall note |
|---|---:|---:|---:|---:|---|
| baseline_dense | 5.00 | 4.60 | 4.90 | 4.00 | Strong baseline; main weakness is answer completeness |
| variant_hybrid | 5.00 | 4.50 | 4.90 | 4.14 | Small completeness gain, but relevance drops slightly |
| variant_dense_rerank | 5.00 | 4.50 | 4.90 | 4.20 | Highest completeness average, but partly affected by missing scores |
| variant_transform_expansion | 5.00 | 4.60 | 4.90 | 4.10 | Most stable improvement with no relevance loss |

### Delta vs baseline
| Variant | Δ Faithfulness | Δ Relevance | Δ Context Recall | Δ Completeness |
|---|---:|---:|---:|---:|
| variant_hybrid | +0.00 | -0.10 | +0.00 | +0.14 |
| variant_dense_rerank | +0.00 | -0.10 | +0.00 | +0.20 |
| variant_transform_expansion | +0.00 | +0.00 | +0.00 | +0.10 |

## 4. Interpretation
### Best overall choice
**Recommended winner: `variant_transform_expansion`.** It preserves the baseline’s Faithfulness, Relevance, and Context Recall, while improving Completeness from **4.00 → 4.10**. This is the cleanest gain because it does not introduce a relevance penalty.

### Why not choose rerank as the final winner?
`variant_dense_rerank` shows the highest completeness average (**4.20**), but the comparison is noisy because several completeness values are `None/NaN` due to LLM judge JSON parsing failures. That makes the average less trustworthy than the query-expansion run.

### Why hybrid is weaker
`variant_hybrid` improves completeness slightly (**+0.14**) but reduces relevance (**-0.10**). This suggests retrieval coverage improved in a few cases, but the final answer became less aligned or less direct for at least one question.

## 5. Per-question observations
### Variant: hybrid
- **gq02 improved in completeness**: score moved from **3 → 4**. Hybrid likely helped retrieve broader supporting context for the remote-work + VPN question.
- **gq09 dropped in relevance**: score moved from **5 → 4** because the answer stated the password rotation rule but omitted the concrete method/path for changing the password.

### Variant: dense + rerank
- No clear semantic wins are visible in the stored scorecards.
- **gq09 relevance dropped from 5 → 4** for the same reason as hybrid: answer was correct but less directly useful.
- Several completeness scores are missing due to judge errors, so the apparent gain should be treated cautiously.

### Variant: transform expansion
- **gq03 completeness improved from 4 → 5** with no loss on other metrics.
- Across the other questions, the scores remain effectively identical to baseline, which indicates this variant is low-risk and stable.

## 6. Main failure pattern across all configs
- **gq05 remains the hardest case**: Relevance = **1** and Completeness = **1** across baseline and all variants. This shows the problem is not mainly retrieval configuration. The likely root cause is answer-generation behavior for insufficient-context / access-control questions rather than chunk ranking.
- Faithfulness stays at **5.00** everywhere, so the system is grounded. The bigger issue is **under-answering** or **answering too narrowly**.

## 7. Evaluation-code issues found in `eval.py`
### 7.1 `compare_ab()` formats deltas incorrectly
Current code uses truthiness checks:
```python
delta = (v_avg - b_avg) if (b_avg and v_avg) else None
b_str = f"{b_avg:.2f}" if b_avg else "N/A"
v_str = f"{v_avg:.2f}" if v_avg else "N/A"
d_str = f"{delta:+.2f}" if delta else "N/A"
```
This is unsafe because `0.0` is treated as false. Use explicit `is not None` checks instead.
```python
delta = (v_avg - b_avg) if (b_avg is not None and v_avg is not None) else None
b_str = f"{b_avg:.2f}" if b_avg is not None else "N/A"
v_str = f"{v_avg:.2f}" if v_avg is not None else "N/A"
d_str = f"{delta:+.2f}" if delta is not None else "N/A"
```

### 7.2 LLM judge sometimes returns invalid JSON
The scorecards contain errors like `LLM scoring error: Unterminated string...`, especially in Completeness. This means the current prompt-only JSON contract is brittle.
Recommended fixes:
- Use structured output / JSON schema when calling the model.
- Add a fallback parser that extracts the first JSON object with regex before `json.loads`.
- Escape long multiline answers or truncate them before sending to the judge.
- Store raw judge output for debugging.

### 7.3 Completeness and relevance depend heavily on answer style
Several answers are factually correct but lose points because they omit supporting conditions such as 'VPN is mandatory', 'Cisco AnyConnect', or the password reset path. This suggests generation prompting should explicitly encourage **short but complete** answers, not just grounded answers.

## 8. Recommended code changes
### 8.1 Fix `compare_ab()`
```python
b_avg = sum(b_scores) / len(b_scores) if b_scores else None
v_avg = sum(v_scores) / len(v_scores) if v_scores else None
delta = (v_avg - b_avg) if (b_avg is not None and v_avg is not None) else None

b_str = f"{b_avg:.2f}" if b_avg is not None else "N/A"
v_str = f"{v_avg:.2f}" if v_avg is not None else "N/A"
d_str = f"{delta:+.2f}" if delta is not None else "N/A"
```

### 8.2 Make the judge output robust
```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    temperature=0,
    response_format={"type": "json_object"},
)
result_text = response.choices[0].message.content
result = json.loads(result_text)
```

### 8.3 Improve answer prompt for completeness
Add generation instructions such as:
- answer directly in the first sentence;
- include all required conditions/exceptions if present in context;
- if evidence is insufficient, abstain explicitly and say which information is missing.

## 9. Final conclusion
The baseline is already very strong on grounding and retrieval recall. The most practical improvement is **query expansion**, because it gives a small but reliable gain in completeness without hurting other metrics. Hybrid and rerank may still be useful, but their current evidence is weaker: hybrid slightly hurts relevance, and rerank is confounded by judge-output failures.

## 10. Final recommendation for the report
Use **baseline_dense** as the control and **variant_transform_expansion** as the final tuned system. In the report, explicitly mention that the next priority is not retrieval faithfulness but **answer completeness** and **judge robustness**.
