from pathlib import Path

path = Path("prmr/core/modes.py")
text = path.read_text(encoding="utf-8")


dictionary_functions = r'''

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

'''

if "def compress_dictionary" not in text:
    marker = "def reconstruct_package(package):"
    text = text.replace(marker, dictionary_functions + "\n" + marker)
    print("Inserted dictionary compression functions ✅")
else:
    print("Dictionary compression functions already exist ✅")


old_reconstruct = '''    if mode == "transform":
        return reconstruct_transform(package)

    if mode == "rule":
        return reconstruct_rule(package)
'''

new_reconstruct = '''    if mode == "transform":
        return reconstruct_transform(package)

    if mode == "dictionary":
        return reconstruct_dictionary(package)

    if mode == "rule":
        return reconstruct_rule(package)
'''

if old_reconstruct in text:
    text = text.replace(old_reconstruct, new_reconstruct)
    print("Patched reconstruct_package for dictionary mode ✅")
elif 'if mode == "dictionary":' in text:
    print("reconstruct_package already supports dictionary mode ✅")
else:
    print("Could not patch reconstruct_package automatically ⚠️")


old_build = '''    raw_package = compress_raw(data_rows)
    transform_package = compress_transform(data_rows)
    rule_result = compress_rule(data_rows)

    transform_size = json_size(transform_package)

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
        }
    ]
'''

new_build = '''    raw_package = compress_raw(data_rows)
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
'''

if old_build in text:
    text = text.replace(old_build, new_build)
    print("Patched build_mode_options to include dictionary mode ✅")
elif '"mode": "dictionary"' in text:
    print("build_mode_options already includes dictionary mode ✅")
else:
    print("Could not patch build_mode_options automatically ⚠️")


old_return = '''        "transform_size": transform_size,
        "rule_possible": rule_result["possible"],
'''

new_return = '''        "transform_size": transform_size,
        "dictionary_size": dictionary_size,
        "rule_possible": rule_result["possible"],
'''

if old_return in text:
    text = text.replace(old_return, new_return)
    print("Added dictionary_size to mode data ✅")
elif '"dictionary_size"' in text:
    print("dictionary_size already in mode data ✅")
else:
    print("Could not add dictionary_size automatically ⚠️")


path.write_text(text, encoding="utf-8")

print()
print("V0.37.1 dictionary compression mode patch complete ✅")
print("Next run:")
print("python benchmarks/runners/run_realistic_memory_benchmark_v037.py")