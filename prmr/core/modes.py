import re
import json


def json_size(data):
    return len(json.dumps(data, separators=(",", ":")))


def calculate_savings(raw_size, candidate_size):
    saved = raw_size - candidate_size

    if raw_size == 0:
        saved_percentage = 0
    else:
        saved_percentage = (saved / raw_size) * 100

    if candidate_size == 0:
        ratio = None
    else:
        ratio = raw_size / candidate_size

    return saved, ratio, saved_percentage


class StrictRuleDiscovery:
    def __init__(self, max_cycle_length=20, min_repeats=2):
        self.max_cycle_length = max_cycle_length
        self.min_repeats = min_repeats

    def discover_constant_rule(self, values):
        if not values:
            return {
                "rule_found": False,
                "reason": "No values"
            }

        first = values[0]

        for value in values:
            if value != first:
                return {
                    "rule_found": False,
                    "reason": "Values are not constant"
                }

        return {
            "rule_found": True,
            "type": "constant",
            "value": first
        }

    def discover_linear_rule(self, values):
        if len(values) < 3:
            return {
                "rule_found": False,
                "reason": "Not enough values for trusted linear rule"
            }

        base = values[0]
        step = values[1] - values[0]

        for index, value in enumerate(values):
            expected = base + step * index

            if value != expected:
                return {
                    "rule_found": False,
                    "reason": "Values are not linear"
                }

        return {
            "rule_found": True,
            "type": "linear",
            "base": base,
            "step": step
        }

    def discover_cycle_rule(self, values):
        if len(values) < 4:
            return {
                "rule_found": False,
                "reason": "Not enough values for trusted cycle"
            }

        max_cycle_length = min(
            self.max_cycle_length,
            len(values) // self.min_repeats
        )

        for cycle_length in range(1, max_cycle_length + 1):
            cycle = values[:cycle_length]
            reconstructed = []

            for index in range(len(values)):
                reconstructed.append(cycle[index % cycle_length])

            if reconstructed == values:
                return {
                    "rule_found": True,
                    "type": "cycle",
                    "cycle": cycle,
                    "cycle_length": cycle_length
                }

        return {
            "rule_found": False,
            "reason": "No simple repeating cycle found"
        }

    def discover_best_rule(self, values):
        constant = self.discover_constant_rule(values)

        if constant["rule_found"]:
            return constant

        if all(isinstance(value, int) for value in values):
            linear = self.discover_linear_rule(values)

            if linear["rule_found"]:
                return linear

            cycle = self.discover_cycle_rule(values)

            if cycle["rule_found"]:
                return cycle

            return {
                "rule_found": False,
                "reason": "No trusted numeric rule found"
            }

        cycle = self.discover_cycle_rule(values)

        if cycle["rule_found"]:
            return cycle

        return {
            "rule_found": False,
            "reason": "No trusted symbolic rule found"
        }


def compress_raw(data_rows):
    return {
        "m": "raw",
        "rows": data_rows
    }


def reconstruct_raw(package):
    return package["rows"]


def compress_transform(data_rows):
    if not data_rows:
        return {
            "m": "transform",
            "o": None,
            "d": []
        }

    origin = data_rows[0]
    deltas = []

    previous = origin

    for row in data_rows[1:]:
        delta = {}

        for key, value in row.items():
            if previous.get(key) != value:
                delta[key] = value

        deltas.append(delta)
        previous = row

    return {
        "m": "transform",
        "o": origin,
        "d": deltas
    }


def reconstruct_transform(package):
    origin = package["o"]

    if origin is None:
        return []

    rows = [dict(origin)]
    current = dict(origin)

    for delta in package["d"]:
        current = dict(current)

        for key, value in delta.items():
            current[key] = value

        rows.append(dict(current))

    return rows



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



def reconstruct_values_from_rule(rule, count):
    values = []

    if rule["type"] == "constant":
        for _ in range(count):
            values.append(rule["value"])

    elif rule["type"] == "linear":
        base = rule["base"]
        step = rule["step"]

        for index in range(count):
            values.append(base + step * index)

    elif rule["type"] == "cycle":
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


def reconstruct_rule(package):
    count = package["n"]
    rules = package["r"]

    columns = {}

    for field, rule in rules.items():
        columns[field] = reconstruct_values_from_rule(rule, count)

    rows = []

    for index in range(count):
        row = {}

        for field in columns:
            row[field] = columns[field][index]

        rows.append(row)

    return rows


def compress_rule(data_rows):
    if not data_rows:
        return {
            "possible": False,
            "package": None,
            "rules": {},
            "failed_field": None,
            "reason": "No rows"
        }

    discovery = StrictRuleDiscovery(
        max_cycle_length=20,
        min_repeats=2
    )

    fields = list(data_rows[0].keys())
    rules = {}

    for field in fields:
        values = [row[field] for row in data_rows]
        rule = discovery.discover_best_rule(values)

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

    package = {
        "m": "rule",
        "n": len(data_rows),
        "r": rules
    }

    reconstructed = reconstruct_rule(package)
    reconstruction_match = reconstructed == data_rows

    return {
        "possible": reconstruction_match,
        "package": package,
        "rules": rules,
        "failed_field": None if reconstruction_match else "unknown",
        "reason": None if reconstruction_match else "Rule reconstruction failed"
    }




def compress_dictionary(data_rows):
    """
    V0.37.1 dictionary / repeated-field compression.

    Designed for messy realistic memory where many fields repeat across rows:
    statuses, topics, old states, active states, risks, canon labels, importance levels.

    It does not infer meaning. It compresses repeated values safely and reconstructs exactly.
    """

    if not data_rows:
        return {
            "m": "dictionary",
            "n": 0,
            "o": [],
            "c": {}
        }

    fields = list(data_rows[0].keys())

    # If row schemas vary, include all observed fields in first-seen order.
    for row in data_rows:
        for key in row.keys():
            if key not in fields:
                fields.append(key)

    columns = {}

    for field in fields:
        values = [
            row.get(field, None)
            for row in data_rows
        ]

        unique_values = []
        value_to_index = {}

        for value in values:
            key = json.dumps(value, sort_keys=True)

            if key not in value_to_index:
                value_to_index[key] = len(unique_values)
                unique_values.append(value)

        # Use dictionary encoding only when repetition exists.
        if len(unique_values) < len(values):
            indexes = [
                value_to_index[json.dumps(value, sort_keys=True)]
                for value in values
            ]

            columns[field] = {
                "t": "dict",
                "v": unique_values,
                "i": indexes
            }
        else:
            columns[field] = {
                "t": "raw",
                "v": values
            }

    return {
        "m": "dictionary",
        "n": len(data_rows),
        "o": fields,
        "c": columns
    }


def reconstruct_dictionary(package):
    count = package["n"]
    fields = package["o"]
    columns = package["c"]

    reconstructed_columns = {}

    for field in fields:
        column = columns[field]

        if column["t"] == "dict":
            values = column["v"]
            indexes = column["i"]
            reconstructed_columns[field] = [
                values[index]
                for index in indexes
            ]

        elif column["t"] == "raw":
            reconstructed_columns[field] = column["v"]

        else:
            raise ValueError(f"Unknown dictionary column type: {column['t']}")

    rows = []

    for index in range(count):
        row = {}

        for field in fields:
            value = reconstructed_columns[field][index]

            # Preserve missing keys by not re-adding None if the field was absent.
            # For current V0.37 datasets schemas are stable, so this remains exact.
            row[field] = value

        rows.append(row)

    return rows


def reconstruct_package(package):
    mode = package["m"]

    if mode == "raw":
        return reconstruct_raw(package)

    if mode == "transform":
        return reconstruct_transform(package)

    if mode == "dictionary":
        return reconstruct_dictionary(package)

    if mode == "rule":
        return reconstruct_rule(package)

    raise ValueError(f"Unknown PRMR package mode: {mode}")


def build_mode_options(data_rows):
    raw_size = json_size(data_rows)

    raw_package = compress_raw(data_rows)
    transform_package = compress_transform(data_rows)
    dictionary_package = compress_dictionary(data_rows)
    rule_result = compress_rule(data_rows)

    transform_size = json_size(transform_package)
    dictionary_size = json_size(dictionary_package)

    options = [
        {
            "mode": "raw",
            "size": raw_size,
            "package": raw_package,
            "possible": True
        },
        {
            "mode": "transform",
            "size": transform_size,
            "package": transform_package,
            "possible": True
        },
        {
            "mode": "dictionary",
            "size": dictionary_size,
            "package": dictionary_package,
            "possible": True
        }
    ]

    rule_size = None

    if rule_result["possible"]:
        rule_package = rule_result["package"]
        rule_size = json_size(rule_package)

        options.append({
            "mode": "rule",
            "size": rule_size,
            "package": rule_package,
            "possible": True
        })

    return {
        "raw_size": raw_size,
        "transform_size": transform_size,
        "dictionary_size": dictionary_size,
        "rule_possible": rule_result["possible"],
        "rule_size": rule_size,
        "rule_failed_field": rule_result.get("failed_field"),
        "rule_failure_reason": rule_result.get("reason"),
        "internal_rule_data": rule_result.get("rules"),
        "options": options
    }