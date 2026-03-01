---
name: csv_analyzer
description: >
  Analyze CSV and Excel files — statistics, filtering, grouping, and
  data previews. Use when the user asks to read, analyze, query, or
  summarize tabular data files (CSV, TSV, Excel).
---

## Instructions

Analyze tabular data files using pandas.

### Prerequisites

Install dependency: `pip install pandas openpyxl`

### Usage

```bash
python {skill_path}/analyze.py PATH [command] [options]
```

Commands:
- `info` (default) — column types, shape, missing values
- `head` — first N rows (default 10)
- `stats` — descriptive statistics for numeric columns
- `query` — filter rows with a pandas query expression
- `groupby` — group-by aggregation
- `columns` — list column names and types

Options:
- `--rows N` — number of rows for head (default 10)
- `--query "col > 100"` — pandas query expression
- `--groupby COL` — column to group by
- `--agg mean|sum|count|min|max` — aggregation function (default: mean)
- `--format json` — output as JSON
- `--columns "col1,col2"` — select specific columns

### Examples

- "Show me what's in data.csv" → `analyze.py data.csv info`
- "First 20 rows of sales.xlsx" → `analyze.py sales.xlsx head --rows 20`
- "Statistics for revenue column" → `analyze.py data.csv stats --columns revenue`
- "Filter rows where age > 30" → `analyze.py data.csv query --query "age > 30"`
- "Average sales by region" → `analyze.py data.csv groupby --groupby region --columns sales --agg mean`

## Resources

| File | Description |
|------|-------------|
| `analyze.py` | Tabular data analyzer |
