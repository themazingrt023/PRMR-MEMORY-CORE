from pathlib import Path

path = Path("prmr/core/engine.py")
text = path.read_text(encoding="utf-8")

if "def looks_like_noise_dataset" not in text:
    marker = "    def compress_and_reconstruct"
    helper = r'''
    def looks_like_noise_dataset(self, rows):
        """
        V0.36.1 noise meaning guardrail.

        This prevents PRMR from treating meaningless high-entropy rows as
        useful memory compression simply because repeated JSON structure saves bytes.

        The aim is not to block all transform compression.
        The aim is to block fake compression on low-meaning/random-noise datasets.
        """
        if not rows or not isinstance(rows, list):
            return False

        if len(rows) < 25:
            return False

        text_values = []
        none_importance_count = 0

        for row in rows:
            if not isinstance(row, dict):
                continue

            if str(row.get("importance", "")).lower() in ("none", "low", "noise"):
                none_importance_count += 1

            for value in row.values():
                if isinstance(value, str):
                    text_values.append(value)

        if not text_values:
            return False

        unique_ratio = len(set(text_values)) / max(len(text_values), 1)

        noise_word_hits = 0
        for value in text_values:
            lower_value = value.lower()
            if (
                "noise" in lower_value
                or "filler" in lower_value
                or "random" in lower_value
                or "irrelevant" in lower_value
                or "duplicate" in lower_value
            ):
                noise_word_hits += 1

        noise_word_ratio = noise_word_hits / max(len(text_values), 1)
        none_importance_ratio = none_importance_count / max(len(rows), 1)

        # High confidence synthetic/noise guardrail.
        if none_importance_ratio >= 0.80 and noise_word_ratio >= 0.50:
            return True

        # Generic high-entropy low-importance guardrail.
        if none_importance_ratio >= 0.90 and unique_ratio >= 0.70:
            return True

        return False

'''

    text = text.replace(marker, helper + "\n" + marker)
    print("Inserted looks_like_noise_dataset helper ✅")
else:
    print("Noise helper already exists ✅")

old = '''        if technical_best["mode"] == "raw":
            policy_option = options[0]
            policy_reason = "Raw mode selected because it is the safest baseline."

        elif technical_percentage < self.minimum_savings_percent:
            policy_option = options[0]
            policy_reason = (
                f"Technical best mode was '{technical_best['mode']}', but savings were "
                f"{round(technical_percentage, 2)}%, below the "
                f"{self.minimum_savings_percent}% threshold."
            )

        else:
            policy_option = technical_best
            policy_reason = (
                f"Selected '{technical_best['mode']}' because it saves "
                f"{round(technical_percentage, 2)}%, meeting the "
                f"{self.minimum_savings_percent}% threshold."
            )
'''

new = '''        noise_guardrail_triggered = self.looks_like_noise_dataset(data_rows)

        if noise_guardrail_triggered:
            policy_option = options[0]
            policy_reason = (
                "Raw mode selected because V0.36.1 noise meaning guardrail detected "
                "high-entropy/low-meaning rows. Byte savings alone are not trusted "
                "as useful continuity compression."
            )

        elif technical_best["mode"] == "raw":
            policy_option = options[0]
            policy_reason = "Raw mode selected because it is the safest baseline."

        elif technical_percentage < self.minimum_savings_percent:
            policy_option = options[0]
            policy_reason = (
                f"Technical best mode was '{technical_best['mode']}', but savings were "
                f"{round(technical_percentage, 2)}%, below the "
                f"{self.minimum_savings_percent}% threshold."
            )

        else:
            policy_option = technical_best
            policy_reason = (
                f"Selected '{technical_best['mode']}' because it saves "
                f"{round(technical_percentage, 2)}%, meeting the "
                f"{self.minimum_savings_percent}% threshold."
            )
'''

if old not in text:
    print("Could not find the exact policy block. It may already be patched or formatted differently.")
else:
    text = text.replace(old, new)
    print("Patched policy block with noise guardrail ✅")

old_return = '''            "minimum_savings_threshold": self.minimum_savings_percent,

            "internal_rule_data": mode_data["internal_rule_data"]
'''

new_return = '''            "minimum_savings_threshold": self.minimum_savings_percent,
            "noise_guardrail_triggered": noise_guardrail_triggered,

            "internal_rule_data": mode_data["internal_rule_data"]
'''

if old_return in text:
    text = text.replace(old_return, new_return)
    print("Added noise_guardrail_triggered to decision output ✅")
elif '"noise_guardrail_triggered"' in text:
    print("noise_guardrail_triggered already in decision output ✅")
else:
    print("Could not patch decision output automatically.")

path.write_text(text, encoding="utf-8")

print("V0.36.1 engine noise guardrail patch complete ✅")