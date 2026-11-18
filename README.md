# ETL_Automation

AI-assisted ETL pipeline that cleans messy student records. It is implemented two ways:

- a **Python script** (`elt_pipeline.py`) that cleans a CSV with pandas and the OpenAI API
- two **n8n workflows** that do the same job from a web upload form

## Project Structure

```
ETL_Automation/
├── elt_pipeline.py                      # Python ETL script (extract -> AI clean -> validate -> save)
├── students_unclean.csv                 # Sample raw input (inconsistent dept, dates, phones, genders...)
├── students_clean.csv                   # Output produced by the pipeline
├── ETL AI AUTOMATION .json              # n8n workflow: Excel upload -> LLM clean -> file
├── ETL AI AUTOMATION Condition.json     # n8n workflow: CSV upload with file-type check, batching, de-duplication
├── requirements.txt                     # Python dependencies
├── .env                                 # OPENAI_API_KEY (local only, git-ignored)
├── .gitignore
├── .gitattributes
└── README.md
```

## Data Schema

`student_id, name, email, phone, dept, dob, city, marks, gender`

## Python Pipeline (`elt_pipeline.py`)

1. **Load**: reads `students_unclean.csv` as strings.
2. **Inspect**: prints the first rows, empty values per column, duplicates, dirty categories and non-numeric marks.
3. **Clean**: removes exact duplicates, then sends rows in batches of 10 to the OpenAI model (`MODEL`, `temperature=0`, JSON output) using a rule-based system prompt.
4. **Validate**: phone and gender are re-applied with deterministic code. Any value the AI wrongly blanked is reported.
5. **Save**: drops duplicate `student_id`s, prints a quality report and writes `students_clean.csv` (UTF-8 with BOM).

### Cleaning rules

| Field | Rule |
|-------|------|
| student_id | `S` + 3 digits (`3` -> `S003`) |
| name | Trimmed, Title Case |
| email | Lowercase; blank if no `@` |
| phone | Strip `+91`, spaces and dashes; keep only 10 digits starting with 6-9 |
| dept | Normalized to `CSE`, `ECE`, `MECH`, `IT`, `CIVIL` |
| dob | `YYYY-MM-DD` |
| city | Title Case; `Bangalore` -> `Bengaluru` |
| marks | Integer 0-100, otherwise blank |
| gender | `Male` / `Female` / blank |

## n8n Workflows

| File | Flow |
|------|------|
| `ETL AI AUTOMATION .json` | Excel Upload -> Extract from File -> LLM Chain (OpenAI) -> Code (JavaScript) -> Convert to File |
| `ETL AI AUTOMATION Condition.json` | CSV Upload -> Check File Type -> Extract from File -> Loop Over Items -> LLM Chain (OpenAI) -> Code (JavaScript) -> Remove Bad Rows -> Remove Duplicates -> Convert to File |

Import either file in n8n via **Workflows -> Import from File**, then attach your OpenAI credentials.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
OPENAI_API_KEY=your_key_here
```

## Usage

```bash
python elt_pipeline.py
```

Reads `students_unclean.csv` and writes `students_clean.csv`.

## Tech Stack

Python, pandas, OpenAI API, python-dotenv, n8n
