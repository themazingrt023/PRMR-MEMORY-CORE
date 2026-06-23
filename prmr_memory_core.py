# PRMR MEMORY CORE V0.03
# Goal:
# Store information as states, transitions, branches, lineage, and reconstruction.
#
# New in V0.03:
# The memory can reconstruct a target state from its origin path.


class PRMRMemory:
    def __init__(self):
        self.states = {}
        self.transitions = []
        self.branches = []
        self.lineage = []

    def add_state(self, key, data):
        self.states[key] = data

    def add_transition(self, from_state, to_state, rule):
        transition = {
            "from": from_state,
            "to": to_state,
            "rule": rule
        }

        self.transitions.append(transition)

        self.lineage.append(
            f"{from_state} → {to_state} because {rule}"
        )

    def add_branch(self, from_state, condition, to_state, rule):
        branch = {
            "from": from_state,
            "condition": condition,
            "to": to_state,
            "rule": rule
        }

        self.branches.append(branch)

        self.lineage.append(
            f"{from_state} → {to_state} under condition {condition} because {rule}"
        )

    def resolve(self, current_state, condition=None):
        for branch in self.branches:
            if (
                branch["from"] == current_state
                and branch["condition"] == condition
            ):
                return branch["to"]

        return current_state

    def show_lineage(self):
        return self.lineage

    def find_cause(self, target_state):
        # First check branches
        for branch in self.branches:
            if branch["to"] == target_state:
                return {
                    "type": "branch",
                    "from": branch["from"],
                    "to": branch["to"],
                    "condition": branch["condition"],
                    "rule": branch["rule"]
                }

        # Then check normal transitions
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
                explanation.append(
                    f"{current} is an origin state. No earlier cause found."
                )
                break

            if cause["type"] == "branch":
                explanation.append(
                    f"{current} exists because {cause['from']} branched under condition {cause['condition']}."
                )
                explanation.append(
                    f"Rule: {cause['rule']}"
                )

            if cause["type"] == "transition":
                explanation.append(
                    f"{current} exists because {cause['from']} became {cause['to']}."
                )
                explanation.append(
                    f"Rule: {cause['rule']}"
                )

            current = cause["from"]

        return explanation

    def get_path_to_origin(self, target_state):
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

        # Reverse so reconstruction starts from origin
        path.reverse()
        return path

    def reconstruct(self, target_state):
        path = self.get_path_to_origin(target_state)

        reconstruction_steps = []
        reconstruction_steps.append(
            f"Starting reconstruction for {target_state}..."
        )

        current_state = None

        for step in path:
            if step["type"] == "origin":
                current_state = step["state"]
                reconstruction_steps.append(
                    f"Origin found: {current_state}"
                )
                reconstruction_steps.append(
                    f"State data: {self.states.get(current_state, 'No data found')}"
                )

            elif step["type"] == "transition":
                reconstruction_steps.append(
                    f"Apply transition: {step['from']} → {step['to']} because {step['rule']}"
                )
                current_state = step["to"]
                reconstruction_steps.append(
                    f"Current reconstructed state: {current_state}"
                )

            elif step["type"] == "branch":
                reconstruction_steps.append(
                    f"Apply branch: {step['from']} → {step['to']} under condition {step['condition']} because {step['rule']}"
                )
                current_state = step["to"]
                reconstruction_steps.append(
                    f"Current reconstructed state: {current_state}"
                )

        reconstruction_steps.append(
            f"Final reconstructed state: {current_state}"
        )

        return reconstruction_steps


# -------------------------
# TEST SYSTEM
# -------------------------

memory = PRMRMemory()

# Add states
memory.add_state("A", "Origin state")
memory.add_state("B", "Expansion state")
memory.add_state("C", "Stabilised state")
memory.add_state("D", "Branch outcome under condition X")
memory.add_state("E", "Branch outcome under condition Y")

# Add transitions
memory.add_transition(
    "A",
    "B",
    "origin expands"
)

memory.add_transition(
    "B",
    "C",
    "expansion stabilises"
)

# Add branches
memory.add_branch(
    "C",
    "X",
    "D",
    "condition X activates the D pathway"
)

memory.add_branch(
    "C",
    "Y",
    "E",
    "condition Y activates the E pathway"
)

# Run branch test
print("Current State: C")
print("Condition: X")
print("Next State:", memory.resolve("C", "X"))

# Show lineage
print("\nFull Lineage:")
for item in memory.show_lineage():
    print(item)

# Ask why D exists
print("\nWhy does D exist?")
for item in memory.why("D"):
    print(item)

# Reconstruct D
print("\nReconstruct D:")
for item in memory.reconstruct("D"):
    print(item)

# Reconstruct E
print("\nReconstruct E:")
for item in memory.reconstruct("E"):
    print(item)