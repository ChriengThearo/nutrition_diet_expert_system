"""CDC 2022 extended BMI-for-age reference, for ages 2 through 19.

Source: https://www.cdc.gov/growthcharts/extended-bmi-data-files.htm
Data: https://www.cdc.gov/growthcharts/data/extended-bmi/bmi-age-2022.csv
The vendored data uses completed months (24.5 represents age 24–24.99 months).
"""

import csv
import math
from functools import lru_cache
from pathlib import Path
from statistics import NormalDist


DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "cdc_bmi_age_2022.csv"


@lru_cache(maxsize=1)
def _reference_rows():
    rows = {}
    with DATA_FILE.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            month_point = float(row["agemos"])
            if month_point != int(month_point) + 0.5:
                continue
            completed_months = int(month_point)
            if 24 <= completed_months <= 239:
                rows[(int(row["sex"]), completed_months)] = {
                    key: float(row[key]) for key in ("L", "M", "S", "sigma", "P5", "P85", "P95")
                }
    if len(rows) != 432:
        raise RuntimeError("The CDC BMI reference is incomplete")
    return rows


def child_bmi_result(age_years, age_months, sex, height_cm, weight_kg):
    """Return BMI, percentile, and CDC category without storing measurements."""
    if type(age_years) is not int or type(age_months) is not int:
        raise ValueError("Enter age in whole years and months.")
    if not 0 <= age_months <= 11:
        raise ValueError("Months must be between 0 and 11.")
    completed_months = age_years * 12 + age_months
    if completed_months < 24 or completed_months > 239:
        raise ValueError("This reference is for ages 2 through 19 only.")
    if sex not in ("male", "female"):
        raise ValueError("Select the sex used by the CDC growth chart.")
    try:
        height_cm = float(height_cm)
        weight_kg = float(weight_kg)
    except (TypeError, ValueError) as exc:
        raise ValueError("Enter valid height and weight measurements.") from exc
    if not (math.isfinite(height_cm) and 50 <= height_cm <= 250
            and math.isfinite(weight_kg) and 5 <= weight_kg <= 300):
        raise ValueError("Enter valid height and weight measurements.")

    bmi = weight_kg / (height_cm / 100) ** 2
    reference = _reference_rows()[(1 if sex == "male" else 2, completed_months)]
    p95 = reference["P95"]
    if bmi <= p95:
        l, m, s = reference["L"], reference["M"], reference["S"]
        z = (((bmi / m) ** l - 1) / (l * s)) if l else math.log(bmi / m) / s
        percentile = 100 * NormalDist().cdf(z)
    else:
        percentile = 90 + 10 * NormalDist().cdf((bmi - p95) / reference["sigma"])

    if bmi < reference["P5"]:
        category = "underweight"
    elif bmi < reference["P85"]:
        category = "healthy_weight"
    elif bmi < p95:
        category = "overweight"
    elif bmi >= min(1.2 * p95, 35):
        category = "severe_obesity"
    else:
        category = "obesity"
    return {"bmi": bmi, "percentile": percentile, "category": category,
            "age_years": age_years, "age_months": age_months}
