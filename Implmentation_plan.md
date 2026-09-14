# Minimal Influencer Scoring Prototype with Simple Web Interface

## Summary

Build a small Python prototype that:

1. Loads candidates from `raw_data.json`.
2. Lets a non-technical user select a candidate through a simple browser interface.
3. Runs deterministic preprocessing and model-assisted interpretation.
4. Displays the score, recommendation, evidence, anomalies, and next action.
5. Saves both JSON and Markdown reports for auditability.

The interface will use lightweight Flask, plain HTML, and CSS. No frontend framework or complex JavaScript will be added.

## Implementation steps

### Step 1: Prepare the Python project

1. Create the application folders:

```text
templates/
static/
outputs/
tests/
```

2. Create the CLI, pipeline, model-adapter, Flask, dependency, and environment files listed below.
3. Keep `raw_data.json` as the only input dataset.

### Step 2: Load and anonymize the selected candidate

1. Load `raw_data.json`.
2. Retrieve one candidate by `account_id`.
3. Use `HQ-110-HIGH-CONVERSION` as the documented demo candidate.
4. Create an anonymized scoring payload before preprocessing or model calls.
5. Exclude `account_id` and `username` from all scoring calculations and model prompts because the mock identifiers contain outcome-like labels such as `BOT`, `POD-SUSPECT`, and `HIGH-CONVERSION`.
6. Use an anonymous identifier such as `candidate_001` inside model prompts.
7. Keep the original identity only as post-decision metadata for display and report filenames.

The pipeline must produce the same score, anomaly flags, model evidence, and recommendation if only the candidate's `account_id` or `username` changes.

### Step 3: Implement deterministic preprocessing

Implement GCC, engagement, commercial-content, anomaly, and hard-rule calculations before model-assisted interpretation and weighted scoring.

### Step 4: Implement model-assisted extraction

Keep local Qwen2.5-14B-Instruct through Transformers as the intended model, but use Gemini Flash-Lite for this laptop because it cannot practically load a 14B model. Use the official `google-genai` SDK for Gemini, validate all model responses with structured schemas, and keep model failures clearly labelled.

### Step 5: Implement scoring and reports

Aggregate deterministic and model-derived signals, apply hard rules before the weighted score, then write JSON and Markdown reports.

### Step 6: Implement and verify the web interface

Connect the Flask routes to the shared pipeline, render the candidate selector and result page, then run the complete test suite and browser demo.

## Application structure

Use this small structure:

```text
main.py                    # CLI entry point
pipeline.py                # preprocessing, scoring, and decision logic
models.py                  # Qwen, Gemini, and reasoning-model adapters
app.py                     # Flask web interface
templates/index.html       # Candidate selection and result page
static/style.css           # Simple readable styling
raw_data.json
requirements.txt
.env.example
tests/
```

The web interface must call the same functions as the CLI. Scoring logic must not be duplicated inside HTML routes.

## Web interface

Run:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

### Main page

Display:

- Boutiqaat Influencer Scoring title
- Candidate dropdown
- Candidate username
- Platform
- Followers
- Category
- GCC audience percentage
- GCC reachable audience
- Run analysis button

The dropdown should use `account_id` values from `raw_data.json`, with `HQ-110-HIGH-CONVERSION` selected by default.

### Results page

Show the result in clear sections:

#### Recommendation banner

Display:

- `ONBOARD`
- `HOLD`
- `PASS`
- `MANUAL REVIEW`

Use visually distinct colors:

```text
ONBOARD       green
HOLD          orange
PASS          red
MANUAL REVIEW purple
```

#### Score summary

Display:

- Final score out of 100
- Audience commercial viability
- Commercialization and intent
- Category and brand alignment
- Content quality and consistency

Use simple horizontal progress bars created with HTML/CSS.

#### Key metrics

Display:

- GCC audience percentage
- GCC reachable audience
- Engagement rate
- Likes-to-comments ratio
- Commercial-content rate
- Anomaly status

#### Reasons

Display:

- Positive signals
- Negative signals
- Anomaly flags
- Model-extracted evidence
- Suggested next action

#### Limitations

Clearly show unavailable or inferred information, such as:

- Verified collaboration rate unavailable
- Post-level volatility unavailable
- Brand sponsorship not proven by brand tags alone
- Fallback model mode, if used

Include a link or button to return to candidate selection.

## Backend routes

Implement only the following routes:

```text
GET /
```

Loads candidates and displays the selection page.

```text
GET /analyze/<account_id>
```

Loads the selected candidate, runs the pipeline, saves reports, and renders the result page.

```text
GET /health
```

Returns a simple JSON response confirming that the application is running.

The interface should use GET requests only. This keeps the prototype simple and avoids unnecessary form-handling complexity.

## Deterministic pipeline

The pipeline remains responsible for:

- Validating input data.
- Calculating GCC audience percentage.
- Calculating GCC reachable audience.
- Calculating engagement rate.
- Calculating likes-to-comments ratio.
- Calculating commercial-content rate.
- Applying anomaly rules.
- Applying hard eligibility rules.
- Calculating the weighted score.
- Producing the final `ONBOARD`, `HOLD`, `PASS`, or `MANUAL REVIEW` decision.

Use the agreed rules:

```text
GCC audience < 45% → PASS
Private account → MANUAL REVIEW
anomaly_detected = true → MANUAL REVIEW
```

Use the agreed score weights:

```text
Audience commercial viability       30%
Commercialization and intent        25%
Category and brand alignment        25%
Content quality and consistency     20%
```

Use the score thresholds:

```text
Score >= 75 → ONBOARD
Score 60–74 → HOLD
Score < 60   → PASS
```

Hard-rule decisions take precedence over the numeric score.

## Model-assisted pipeline

### Qwen2.5-14B-Instruct via Transformers

Load Qwen locally with `AutoModelForCausalLM` and `AutoTokenizer` for post-level caption interpretation when suitable hardware is available. On the current laptop, leave Qwen disabled and use Gemini Flash-Lite instead.

- Commercial intent
- CTA detection
- Discount-code detection
- Restock detection
- Product-review detection
- Unboxing detection
- Product education
- Sales framing
- Evidence extraction

Return structured JSON.

### Gemini Flash-Lite via the official `google-genai` SDK

Use Gemini Flash-Lite for this implementation and use Gemini for:

- Brand classification
- Product category
- Prestige tier
- Boutiqaat catalog fit
- Brand/category ambiguity

Keep the provider layer intentionally small: one `run_qwen()` function for local Qwen inference and one `run_gemini()` function for Gemini inference. Prompt construction, response validation, and fallback handling remain outside these provider-call functions.

A tagged brand must not automatically be treated as a verified sponsorship.

### Larger reasoning model

Use a larger Gemini model for the final explanation.

It receives the calculated evidence and produces:

- Main recommendation explanation
- Main positive signals
- Main negative signals
- Trade-off analysis
- Suggested next action

The larger model must not change the calculated score or decision.

## Output files

For each analysis, save:

```text
outputs/<account_id>.json
outputs/<account_id>.md
```

The web page should read the result returned by the pipeline directly. The JSON and Markdown files should remain available for auditability and submission evidence.

JSON should contain:

- Candidate identity
- Derived metrics
- Anomaly flags
- Model evidence
- Score breakdown
- Final score
- Decision
- Model status
- Limitations

Markdown should contain the same information in a human-readable report format.

## Styling requirements

Use plain CSS only:

- Responsive centered layout
- White cards on a light background
- Clear typography
- Large recommendation banner
- Readable tables
- Progress bars
- Color-coded badges
- No charting library
- No frontend framework
- No complex JavaScript

The interface should remain usable on a laptop screen without technical knowledge.

## Tests and acceptance criteria

Test the pipeline independently from Flask:

- GCC percentage calculation.
- GCC reachable audience calculation.
- Engagement-rate calculation.
- Likes-to-comments ratio.
- Zero-comment handling.
- Commercial-content rate.
- GCC below 45% produces `PASS`.
- Anomaly flag produces `MANUAL REVIEW`.
- Private account produces `MANUAL REVIEW`.
- HQ-110 produces a strong recommendation.
- HQ-102 fails the GCC eligibility rule.
- HQ-109 produces manual review because of the anomaly flag.
- JSON and Markdown reports are generated.
- Changing `account_id` does not change the score or recommendation.
- Changing `username` does not change the score or recommendation.
- Outcome-like identifier text is not included in model prompts.

Test the web interface:

- `/` loads successfully.
- Candidate dropdown contains all 10 accounts.
- Default candidate is HQ-110.
- `/analyze/HQ-110-HIGH-CONVERSION` displays a result.
- Unknown account IDs return a friendly error page.
- `/health` returns a successful response.
- No model/API key still allows the interface to run in clearly labelled fallback mode.

End-to-end demo:

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

Select a candidate, run the analysis, and show the recommendation with its evidence and limitations.

## Explicit assumptions

- Flask is acceptable as the only web dependency.
- HTML and CSS are intentionally simple.
- The browser interface and CLI use the same pipeline.
- No database is required.
- No scraping or paid external data source is added.
- The current mock data cannot prove verified collaborations.
- The current mock data cannot support real post-performance volatility.
- Model failures use clearly labelled fallback behavior.
- The Python score remains the source of truth.
- The web interface is for viewing and selecting candidates, not for editing data.
