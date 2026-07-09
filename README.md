## Usage

To use the deduplication function of the ICD-9 code, import all functions from deduplication and customize which function you want to use.

Example:
Pass a list of raw ICD-9 codes to the `de_duplicate_icd9` function to get the deduplicated ICD-9 codes.

```python
import deduplicate

def de_duplicate_icd9(input_code : list[str]) -> list[str]:
    # 1. Remove invalid codes
    code = deduplicate.remove_invalid_code(input_code)
    
    # 2. If there is more detailed code -> remove less digit code
    dedup_code = deduplicate.remove_less_detailed_code(code)
    
    # 3. If code has include code -> remove include code
    dedup_code = deduplicate.remove_include_code(dedup_code)
    
    # 4. Collapse two code into one code
    dedup_code = deduplicate.collapse_combine_code(dedup_code)
    
    # 5. Check for codes that require clinical review
    deduplicate.alert_reconsider_code(dedup_code)
    
    return dedup_code

# Example usage:
raw_codes = ["1733", "1735"]
cleaned_codes = de_duplicate_icd9(raw_codes)
cleaned_codes
```

## Evaluation of inclusion mapping
This evaluation was conducted using **Gemini 3.5 Flash** (via [ai_check.ipynb](script/ai_check.ipynb)) 

📊 **[View the Inclusion Mapping Workflow Diagram](result/inclusionMapping_diagram.html)**
- **Total Rows Evaluated:** 135
- **Total Correct Mappings:** 34
- **Overall Accuracy:** 25.19%

### Performance per Method
The table below displays the accuracy across different mapping methods. Note that since maps can be found by multiple methods simultaneously, the sum of individual predictions may exceed unique row totals.

| Method | Total Predictions | Correct Predictions | Accuracy (%) |
| :--- | :---: | :---: | :---: |
| **TFIDF** | 51 | 30 | 58.82% |
| **LavenDist** | 64 | 23 | 35.94% |
| **PubMedBERT** | 124 | 32 | 25.81% |