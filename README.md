# Gender Bias Analysis

A Streamlit application for comparing gender-pronoun results from AI models.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
colima start
streamlit run app.py
```

## Input

Upload the merged 2-option and 3-option CSV files together. Required columns:

- `category`, `sub-category`, `sentence`
- `biased pronoun` (the human-assigned stereotype baseline)
- `options`, `model`
- `round1` through `round10`

Accepted answers are `He`, `She`, `He/She`, and `Reject`.

## Analysis

- Gender distribution and dominance
- Stereotype alignment (not accuracy)
- Fair matched 2-option versus 3-option comparison
- Model, category, and subcategory comparisons
- Neutral and rejection rates
- Ten-round consistency
- Complete rejected-sentence and shared-rejection tables
- Data-quality checks and model-name standardization

All interface filters also apply to the generated reports.

## PDF reports

1. General Summary
2. 2-Option vs 3-Option
3. Model Comparison
4. Category and Subcategory
5. Stereotype Alignment
6. Rejection and Consistency

Every report ends with a calculation guide explaining its terms and methodology.
