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

diagnostics = table_values(16, "IX", "X")
assert len(diagnostics) == 27
for chart, paper_rows in [("no-intervention", [2, 3, 4, 5, 6]), ("relational-action", [7, 8]), ("cross-task", [0, 1])]:
    for group, paper_row in zip(data["charts"][chart]["groups"], paper_rows, strict=True):
        for policy_index, policy in enumerate(policies):
            assert group["series"][policy]["result"] == diagnostics[paper_row * 3 + policy_index], (chart, group["label"], policy)
            checked += 1

assert checked == 84

# Figure 11 embeds six lossless chart images. Check the failure-mode counts
# against their original segment colors, not a rendered/screenshot estimate.
# Every failure occupies an equal-width slice of the normalized bar; checking
# two interior points in each slice detects a one-count boundary discrepancy.
failure_chart = data["charts"]["failures"]
images = {image.name: image.image.convert("RGB") for image in reader.pages[8].images}
colors = [tuple(bytes.fromhex(mode["color"][1:])) for mode in failure_chart["modes"]]
segments = 0
for group_index, group in enumerate(failure_chart["groups"]):
    image = images[group["paperImage"]]
    for policy_index, policy in enumerate(policies):
        series = group["series"][policy]
        failures, counts = series["failures"], series["counts"]
        ood = data["charts"]["tasks"]["groups"][group_index]["series"][policy]["ood"]
        assert failures == ood[1] - ood[0]
        assert len(counts) == len(colors) and all(isinstance(count, int) and count >= 0 for count in counts)
        assert sum(counts) == failures
        expected_slices = [mode_index for mode_index, count in enumerate(counts) for _ in range(count)]
        for slice_index, expected_mode in enumerate(expected_slices):
            for offset in [0.35, 0.65]:
                x = round(87.5 + (slice_index + offset) / failures * 376)
                rgb = image.getpixel((x, [72, 135, 199][policy_index]))
                distances = [sum((a-b)**2 for a, b in zip(rgb, color, strict=True)) for color in colors]
                observed_mode = min(range(len(colors)), key=distances.__getitem__)
                assert observed_mode == expected_mode, ("Figure 11", group["label"], policy, slice_index, expected_mode, observed_mode)
        segments += sum(count > 0 for count in counts)

# Reconcile the explicitly stated counts in Section V-F (PDF page 8).
assert sum(group["series"][policy]["counts"][2] for group in failure_chart["groups"][:1] for policy in policies) == 148
assert sum(failure_chart["groups"][1]["series"][policy]["counts"][0] for policy in policies) == 74
assert sum(failure_chart["groups"][3]["series"][policy]["counts"][1] for policy in policies) == 75
print(f"Verified {checked} success bars against Tables IV, VI–IX (counts, rates, and CI bounds), and all {segments} nonzero failure segments against Figure 11.")
