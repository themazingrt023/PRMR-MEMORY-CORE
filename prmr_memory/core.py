class PRMRCoreMemory:
    def __init__(self):
        self.states = {}
        self.transitions = []
        self.branches = []

    def add_state(self, key, data):
        self.states[key] = data

    def add_transition(self, from_state, to_state, rule):
        self.transitions.append({
            "from": from_state,
            "to": to_state,
            "rule": rule
        })

    def add_branch(self, from_state, condition, to_state, rule):
        self.branches.append({
            "from": from_state,
            "condition": condition,
            "to": to_state,
            "rule": rule
        })

    def find_cause(self, target_state):
        for branch in self.branches:
            if branch["to"] == target_state:
                return {
                    "type": "branch",
                    "from": branch["from"],
                    "to": branch["to"],
                    "condition": branch["condition"],
                    "rule": branch["rule"]
                }

        for transition in self.transitions:
            if transition["to"] == target_state:
                return {
                    "type": "transition",
                    "from": transition["from"],
                    "to": transition["to"],
                    "rule": transition["rule"]
                }

        return None

    def why(self, target_state):
        explanation = []
        current = target_state

        while True:
            cause = self.find_cause(current)

            if cause is None:
                explanation.append(f"{current} is an origin state.")
                break

            if cause["type"] == "branch":
                explanation.append(
                    f"{current} exists because {cause['from']} branched under condition {cause['condition']}."
                )
                explanation.append(f"Rule: {cause['rule']}")

            elif cause["type"] == "transition":
                explanation.append(
                    f"{current} exists because {cause['from']} became {cause['to']}."
                )
                explanation.append(f"Rule: {cause['rule']}")

            current = cause["from"]

        return explanation

    def reconstruct(self, target_state):
        path = []
        current = target_state

        while True:
            cause = self.find_cause(current)

            if cause is None:
                path.append({
                    "type": "origin",
                    "state": current
                })
                break

            path.append(cause)
            current = cause["from"]

        path.reverse()

        steps = []
        current_state = None

        for step in path:
            if step["type"] == "origin":
                current_state = step["state"]
                steps.append(f"Origin found: {current_state}")

            elif step["type"] == "transition":
                current_state = step["to"]
                steps.append(
                    f"Apply transition: {step['from']} → {step['to']} because {step['rule']}"
                )

            elif step["type"] == "branch":
                current_state = step["to"]
                steps.append(
                    f"Apply branch: {step['from']} → {step['to']} under condition {step['condition']} because {step['rule']}"
                )

        steps.append(f"Final reconstructed state: {current_state}")

        return steps