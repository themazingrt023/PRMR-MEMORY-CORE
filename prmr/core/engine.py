from prmr.core.modes import (
    build_mode_options,
    calculate_savings,
    reconstruct_package
)

from prmr.security.output_policy import MINIMUM_SAVINGS_PERCENT


class PRMRMemoryCore:
    def __init__(self, minimum_savings_percent=MINIMUM_SAVINGS_PERCENT):
        self.minimum_savings_percent = minimum_savings_percent


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


    def compress_and_reconstruct(self, data_rows):
        mode_data = build_mode_options(data_rows)

        raw_size = mode_data["raw_size"]
        options = mode_data["options"]

        possible_options = [
            option for option in options
            if option["possible"]
        ]

        technical_best = min(
            possible_options,
            key=lambda option: option["size"]
        )

        technical_saved, technical_ratio, technical_percentage = calculate_savings(
            raw_size,
            technical_best["size"]
        )

        noise_guardrail_triggered = self.looks_like_noise_dataset(data_rows)

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

        reconstructed_rows = reconstruct_package(policy_option["package"])
        reconstruction_match = reconstructed_rows == data_rows

        policy_saved, policy_ratio, policy_percentage = calculate_savings(
            raw_size,
            policy_option["size"]
        )

        return {
            "raw_size": raw_size,
            "transform_size": mode_data["transform_size"],
            "rule_possible": mode_data["rule_possible"],
            "rule_size": mode_data["rule_size"],
            "rule_failed_field": mode_data["rule_failed_field"],
            "rule_failure_reason": mode_data["rule_failure_reason"],

            "technical_best_mode": technical_best["mode"],
            "technical_best_size": technical_best["size"],
            "technical_saved_bytes": technical_saved,
            "technical_compression_ratio": technical_ratio,
            "technical_saved_percentage": technical_percentage,

            "policy_mode": policy_option["mode"],
            "policy_size": policy_option["size"],
            "policy_reason": policy_reason,
            "policy_saved_bytes": policy_saved,
            "policy_compression_ratio": policy_ratio,
            "policy_saved_percentage": policy_percentage,

            "compressed_package": policy_option["package"],
            "reconstructed_rows": reconstructed_rows,
            "reconstruction_match": reconstruction_match,
            "minimum_savings_threshold": self.minimum_savings_percent,
            "noise_guardrail_triggered": noise_guardrail_triggered,

            "internal_rule_data": mode_data["internal_rule_data"]
        }

    def run_dataset(self, dataset_name, description, rows):
        decision = self.compress_and_reconstruct(rows)

        return {
            "dataset": dataset_name,
            "description": description,
            "row_count": len(rows),
            "decision": decision
        }

    def run(self, datasets):
        results = []

        for dataset in datasets:
            result = self.run_dataset(
                dataset["name"],
                dataset["description"],
                dataset["rows"]
            )

            results.append(result)

        all_reconstructions_verified = all(
            result["decision"]["reconstruction_match"]
            for result in results
        )

        return {
            "version": "0.28",
            "all_reconstructions_verified": all_reconstructions_verified,
            "results": results
        }