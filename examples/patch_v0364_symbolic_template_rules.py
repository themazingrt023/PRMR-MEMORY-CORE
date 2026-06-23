from pathlib import Path

path = Path("prmr/core/modes.py")
text = path.read_text(encoding="utf-8")

# Add regex support if missing.
if "import re" not in text:
    text = "import re\n" + text
    print("Added import re ✅")
else:
    print("import re already present ✅")


# Insert helper before reconstruct_values_from_rule.
helper_marker = "def reconstruct_values_from_rule(rule, count):"

helper = r'''
def discover_string_numeric_template(values):
    """
    V0.36.4 symbolic template rule discovery.

    Detects sequences such as:
        Atlas Branch 1
        Atlas Branch 2
        Atlas Branch 3

    and compresses them as:
        prefix = "Atlas Branch "
        base = 1
        step = 1
        suffix = ""

    This strengthens rule-mode compression without trusting arbitrary text.
    It only accepts a rule if exact reconstruction matches every value.
    """

    if not values or len(values) < 3:
        return {
            "rule_found": False,
            "reason": "Not enough values for symbolic template rule"
        }

    if not all(isinstance(value, str) for value in values):
        return {
            "rule_found": False,
            "reason": "Symbolic template requires all values to be strings"
        }

    parsed = []

    for value in values:
        match = re.match(r"^(.*?)(-?\d+)(.*?)$", value)

        if not match:
            return {
                "rule_found": False,
                "reason": "No trusted symbolic rule found"
            }

        prefix, number_text, suffix = match.groups()

        parsed.append({
            "prefix": prefix,
            "number_text": number_text,
            "number": int(number_text),
            "suffix": suffix
        })

    first_prefix = parsed[0]["prefix"]
    first_suffix = parsed[0]["suffix"]

    if any(item["prefix"] != first_prefix or item["suffix"] != first_suffix for item in parsed):
        return {
            "rule_found": False,
            "reason": "Symbolic template prefix/suffix mismatch"
        }

    numbers = [item["number"] for item in parsed]

    steps = [
        numbers[index] - numbers[index - 1]
        for index in range(1, len(numbers))
    ]

    if not steps:
        return {
            "rule_found": False,
            "reason": "Not enough values for symbolic template step"
        }

    step = steps[0]

    if step == 0:
        return {
            "rule_found": False,
            "reason": "Symbolic template step is zero; constant rule should handle this"
        }

    if any(current_step != step for current_step in steps):
        return {
            "rule_found": False,
            "reason": "Symbolic numeric sequence is not linear"
        }

    number_widths = [len(item["number_text"].lstrip("-")) for item in parsed]
    uses_zero_padding = any(
        item["number_text"].lstrip("-").startswith("0")
        for item in parsed
    )

    width = number_widths[0] if uses_zero_padding and len(set(number_widths)) == 1 else None

    def format_number(number):
        if width is None:
            return str(number)

        if number < 0:
            return "-" + str(abs(number)).zfill(width)

        return str(number).zfill(width)

    reconstructed = [
        first_prefix + format_number(numbers[0] + step * index) + first_suffix
        for index in range(len(values))
    ]

    if reconstructed != values:
        return {
            "rule_found": False,
            "reason": "Symbolic template reconstruction failed"
        }

    return {
        "rule_found": True,
        "type": "string_numeric_template",
        "prefix": first_prefix,
        "suffix": first_suffix,
        "base": numbers[0],
        "step": step,
        "width": width,
        "reason": "Symbolic numeric template rule discovered"
    }


'''

if "def discover_string_numeric_template" not in text:
    text = text.replace(helper_marker, helper + "\n" + helper_marker)
    print("Inserted discover_string_numeric_template helper ✅")
else:
    print("Symbolic template helper already exists ✅")


# Patch reconstruction.
old_reconstruct_block = '''    elif rule["type"] == "cycle":
        cycle = rule["cycle"]

        for index in range(count):
            values.append(cycle[index % len(cycle)])

    return values
'''

new_reconstruct_block = '''    elif rule["type"] == "cycle":
        cycle = rule["cycle"]

        for index in range(count):
            values.append(cycle[index % len(cycle)])

    elif rule["type"] == "string_numeric_template":
        prefix = rule["prefix"]
        suffix = rule["suffix"]
        base = rule["base"]
        step = rule["step"]
        width = rule.get("width")

        for index in range(count):
            number = base + step * index

            if width is None:
                number_text = str(number)
            elif number < 0:
                number_text = "-" + str(abs(number)).zfill(width)
            else:
                number_text = str(number).zfill(width)

            values.append(prefix + number_text + suffix)

    return values
'''

if old_reconstruct_block in text and "string_numeric_template" not in text[text.index("def reconstruct_values_from_rule"):text.index("def reconstruct_rule")]:
    text = text.replace(old_reconstruct_block, new_reconstruct_block)
    print("Patched reconstruct_values_from_rule ✅")
else:
    print("Reconstruction block already patched or exact block not found ⚠️")


# Patch compress_rule fallback.
old_rule_discovery_block = '''        rule = discovery.discover_best_rule(values)

        if not rule["rule_found"]:
            return {
                "possible": False,
                "package": None,
                "rules": rules,
                "failed_field": field,
                "reason": rule["reason"]
            }

        rules[field] = rule
'''

new_rule_discovery_block = '''        rule = discovery.discover_best_rule(values)

        if not rule["rule_found"]:
            symbolic_rule = discover_string_numeric_template(values)

            if symbolic_rule["rule_found"]:
                rule = symbolic_rule

        if not rule["rule_found"]:
            return {
                "possible": False,
                "package": None,
                "rules": rules,
                "failed_field": field,
                "reason": rule["reason"]
            }

        rules[field] = rule
'''

if old_rule_discovery_block in text:
    text = text.replace(old_rule_discovery_block, new_rule_discovery_block)
    print("Patched compress_rule symbolic fallback ✅")
elif "symbolic_rule = discover_string_numeric_template(values)" in text:
    print("compress_rule symbolic fallback already exists ✅")
else:
    print("Could not patch compress_rule automatically ⚠️")

path.write_text(text, encoding="utf-8")

print()
print("V0.36.4 symbolic template rule patch complete ✅")
print("Next run:")
print("python benchmarks/runners/run_trust_suite_v036.py")