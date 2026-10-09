"""Verify every interactive-chart value against the downloadable paper (requires pypdf)."""
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader

docs = Path(__file__).resolve().parents[1]
paper = docs / "spa-bench-paper.pdf"
data = json.loads((docs / "assets/results-chart-data.json").read_text())
assert hashlib.sha256(paper.read_bytes()).hexdigest() == data["source"]["sha256"], "Paper version changed; review chart data."
reader = PdfReader(paper)


def table_values(page, number, next_number):
    text = reader.pages[page - 1].extract_text()
    block = re.split(r"TABLE\s*" + number + r"\b", text, maxsplit=1)[1]
    block = re.split(r"TABLE\s*" + next_number + r"\b", block, maxsplit=1)[0]
    pattern = r"(\d+)/(\d+)\s*[;(]\s*([\d.]+)%\s*[,\s(]+([\d.]+)\s*[–−-]\s*([\d.]+)"
    return [[int(a), int(b), float(c), float(d), float(e)] for a, b, c, d, e in re.findall(pattern, block)]


policies = [policy["id"] for policy in data["policies"]]
aggregate = table_values(15, "IV", "V")
assert len(aggregate) == 12
checked = 0
for group_index, paper_column in enumerate([3, 0, 1]):
    for policy_index, policy in enumerate(policies):
        value = data["charts"]["aggregate"]["groups"][group_index]["series"][policy]["result"]
        assert value == aggregate[policy_index * 4 + paper_column], ("aggregate", policy, group_index, value)
        checked += 1

for variant, number, next_number in [("ood", "VI", "VII"), ("direct", "VII", "VIII")]:
    values = table_values(15, number, next_number)
    assert len(values) == 18, (number, len(values))
    for group_index, group in enumerate(data["charts"]["tasks"]["groups"]):
        for policy_index, policy in enumerate(policies):
            assert group["series"][policy][variant] == values[group_index * 3 + policy_index], (number, group["label"], policy)
            checked += 1

paraphrase = table_values(16, "VIII", "IX")
assert len(paraphrase) == 12
for group_index, group in enumerate(data["charts"]["paraphrasing"]["groups"]):
    for variant_index, variant in enumerate(["original", "paraphrased"]):
        for policy_index, policy in enumerate(policies):
            assert group["series"][policy][variant] == paraphrase[(group_index * 2 + variant_index) * 3 + policy_index], ("paraphrasing", group["label"], policy, variant)
            checked += 1

# Check that task-level totals agree with the aggregate result shown elsewhere.
for policy in policies:
    for variant, aggregate_index in [("ood", 2), ("direct", 0)]:
        task_values = [group["series"][policy][variant] for group in data["charts"]["tasks"]["groups"]]
        total = data["charts"]["aggregate"]["groups"][aggregate_index]["series"][policy]["result"]
        assert [sum(value[index] for value in task_values) for index in [0, 1]] == total[:2]

assert checked == 57
print(f"Verified all {checked} bars against paper Tables IV, VI, VII, and VIII, including counts, rates, and both CI bounds.")
