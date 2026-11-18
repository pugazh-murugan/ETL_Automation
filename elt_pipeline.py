import pandas as pd
import json
from dotenv import load_dotenv
from openai import OpenAI
import re

INPUT_FILE = "students_unclean.csv"
load_dotenv()
client = OpenAI()          # reads OPENAI_API_KEY from .env
MODEL = "gpt-5.4-mini"
BATCH_SIZE = 10
# STEP 1: Load the file
df = pd.read_csv(INPUT_FILE, dtype=str, keep_default_na=False)
print("Loaded OK ->", INPUT_FILE)
print("Rows:", len(df), "| Columns:", len(df.columns))

# STEP 2: Read / inspect the data
print("\n--- First 10 rows ---")
print(df.head(10).to_string())

print("\n--- Column names ---")
print(list(df.columns))

print("\n--- Empty values per column ---")
print((df.apply(lambda c: c.str.strip() == "")).sum())

print("\n--- Duplicate rows ---")
print("Exact duplicates:", df.duplicated().sum())

print("\n--- Unique values (dirty categories) ---")
for col in ["dept", "gender", "city"]:
    print(f"\n{col}:")
    print(df[col].str.strip().value_counts().to_string())

print("\n--- Marks values that are not numbers ---")
bad_marks = df[~df["marks"].str.replace("%", "").str.strip().str.isdigit()]
print(bad_marks[["student_id", "name", "marks"]].to_string())

# STEP 3: Clean the data with OpenAI
SYSTEM_PROMPT = """You are a data-cleaning assistant for a student records table.
You receive JSON: {"rows": [ {student_id,name,email,phone,dept,dob,city,marks,gender}, ... ]}
Return JSON: {"rows": [ ... ]} with the SAME number of rows, in the SAME order, with the SAME keys.
Only return "" when a rule below says so. Do NOT blank a value that can be converted.

Rules:
- student_id: "S" + 3 digits. "3" -> "S003", "S004" stays "S004".
- name: trim, collapse repeated spaces, Title Case.
- email: lowercase, trimmed. If empty or has no "@", return "".
- phone: remove +91, spaces, dashes. Keep the remaining number if it is exactly 10 digits
  and starts with 6-9. Otherwise "".
  Examples: "98765 42542" -> "9876542542"; "+91-9885893910" -> "9885893910"; "12345" -> "".
- dept mapping (always convert): CSE/cse/Computer Science -> "CSE";
  ECE/ece/Electronics -> "ECE"; MECH/Mechanical -> "MECH";
  IT/it/Information Tech -> "IT"; Civil -> "CIVIL".
- dob: ALWAYS convert to YYYY-MM-DD. Slash/dash dates are DD/MM/YYYY or DD-MM-YYYY.
  Examples: "12-05-2002" -> "2002-05-12"; "07/09/2001" -> "2001-09-07";
  "2001/07/23" -> "2001-07-23"; "15 Aug 2002" -> "2002-08-15"; "2003-01-30" stays.
- city: trim, Title Case; "Bangalore" and "Bengaluru" -> "Bengaluru".
- marks: integer 0-100 (remove "%"). If empty, "NA", text, negative or above 100 -> "".
- gender mapping (always convert): M/male/Male -> "Male"; F/female/Female -> "Female";
  empty -> "".
Never invent data. Output only the JSON object."""

def clean_batch(rows):
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"rows": rows})},
        ],
    )
    out = json.loads(response.choices[0].message.content)["rows"]
    if len(out) != len(rows):
        raise ValueError(f"Expected {len(rows)} rows, got {len(out)}")
    return out

# Remove exact duplicates first (saves tokens)
df = df.drop_duplicates().reset_index(drop=True)
print("\nAfter removing duplicates:", len(df), "rows")

records = df.to_dict(orient="records")
cleaned = []
for i in range(0, len(records), BATCH_SIZE):
    batch = records[i:i + BATCH_SIZE]
    cleaned.extend(clean_batch(batch))
    print(f"Cleaned rows {i + 1} to {i + len(batch)}")

clean_df = pd.DataFrame(cleaned, columns=df.columns)
def fix_phone(raw):
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("91"):   # +91 prefix
        digits = digits[2:]
    return digits if re.fullmatch(r"[6-9]\d{9}", digits) else ""

clean_df["phone"] = df["phone"].apply(fix_phone)
# Gender: deterministic mapping (no guessing from names)
GENDER_MAP = {"m": "Male", "male": "Male", "f": "Female", "female": "Female"}
clean_df["gender"] = df["gender"].str.strip().str.lower().map(GENDER_MAP).fillna("")
def find_problems(raw_df, clean_df):
    problems = []
    for r, c in zip(raw_df.to_dict("records"), clean_df.to_dict("records")):
        if r["gender"].strip() and not c["gender"]:
            problems.append((r["student_id"], "gender", r["gender"]))
        if r["dob"].strip() and not c["dob"]:
            problems.append((r["student_id"], "dob", r["dob"]))
        digits = re.sub(r"\D", "", r["phone"])[-10:]
        if re.fullmatch(r"[6-9]\d{9}", digits) and not c["phone"]:
            problems.append((r["student_id"], "phone", r["phone"]))
    return problems

problems = find_problems(df, clean_df)
print("\nWrongly blanked values:", len(problems))
for p in problems:
    print(p)

# STEP 4: Final checks and save the clean CSV
OUTPUT_FILE = "students_clean.csv"

# Remove duplicates that only appear after cleaning (e.g. same student_id)
before = len(clean_df)
clean_df = clean_df.drop_duplicates(subset="student_id").reset_index(drop=True)
print(f"\nDuplicates removed after cleaning: {before - len(clean_df)}")

# Quick quality report
clean_df["city"] = clean_df["city"].str.strip().replace({"Bangalore": "Bengaluru"})
print("\n--- Final quality report ---")
print("Rows:", len(clean_df))
print("Empty values per column:")
print((clean_df == "").sum().to_string())
print("\nDept values:  ", sorted(clean_df["dept"].unique()))
print("Gender values:", sorted(clean_df["gender"].unique()))
print("City values:  ", sorted(clean_df["city"].unique()))

# Save
clean_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
print(f"\nSaved final file -> {OUTPUT_FILE}")