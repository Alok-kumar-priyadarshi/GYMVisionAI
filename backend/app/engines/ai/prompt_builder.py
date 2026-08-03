# file_name: prompt_builder.py

"""Prompt construction.

Implements ``prompts/01_PROMPT_ARCHITECTURE.md`` and the templates in
``prompts/02_SYSTEM_PROMPT.md`` through ``prompts/08_SAFETY_GUARDRAILS.md``.

The Prompt Builder receives exactly one Context Package and returns a validated
prompt. Per ``instructions/04_AI_RULES.md`` section 5 it never retrieves data,
never calls a repository and never talks to a provider.

Templates live in ``configuration/prompts`` so prompts are not hardcoded inside
application services, which section 20 of the AI Architecture forbids.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.engines.ai.context_package import ContextPackage, Intent
from app.shared.exceptions import PromptConstructionError

logger = logging.getLogger(__name__)

PROMPT_CONFIGURATION_FILE = (
    Path(__file__).resolve().parents[3] / "configuration" / "prompts" / "templates.yaml"
)

MAX_PROMPT_CHARACTERS = 24_000
"""Upper bound on an assembled prompt, guarding against runaway context."""


@dataclass(frozen=True, slots=True)
class Prompt:
    """A validated prompt, ready for a provider."""

    system: str
    user: str
    intent: Intent
    version: str

    @property
    def size(self) -> int:
        """Return the combined character length."""
        return len(self.system) + len(self.user)


class PromptBuilder:
    """Assembles prompts from templates and a Context Package."""

    def __init__(self, templates: dict) -> None:
        self._templates = templates
        self._version = templates.get("version", "1.0.0")
        self._system = templates["system_prompt"].strip()
        self._tasks = templates["task_prompts"]

    def build(self, package: ContextPackage, request: str = "") -> Prompt:
        """Assemble the prompt for one request.

        Args:
            package: The only source of context, per the Context Package contract.
            request: The user's message, for conversational intents.

        Returns:
            A validated prompt.

        Raises:
            PromptConstructionError: If the intent has no template or the
                assembled prompt fails validation.
        """
        try:
            task = self._tasks[str(package.intent)].strip()
        except KeyError as error:
            logger.error("No prompt template for intent.")
            raise PromptConstructionError() from error

        sections = [task, self._render_context(package)]
        if request.strip():
            sections.append(f"# User Request\n{request.strip()}")

        user_prompt = "\n\n".join(part for part in sections if part)
        prompt = Prompt(
            system=self._system,
            user=user_prompt,
            intent=package.intent,
            version=self._version,
        )

        self._validate(prompt)
        # The prompt body is never logged: it carries user context.
        logger.debug(
            "Prompt built: intent=%s sections=%s size=%d",
            package.intent,
            ",".join(package.sections()),
            prompt.size,
        )
        return prompt

    @staticmethod
    def _validate(prompt: Prompt) -> None:
        """Reject a prompt that cannot safely be sent.

        Raises:
            PromptConstructionError: If the prompt is empty or oversized.
        """
        if not prompt.system.strip() or not prompt.user.strip():
            raise PromptConstructionError()
        if prompt.size > MAX_PROMPT_CHARACTERS:
            logger.error("Prompt exceeded the maximum size.")
            raise PromptConstructionError()

    def _render_context(self, package: ContextPackage) -> str:
        """Render the Context Package as readable prompt sections.

        Sections appear in a fixed order so the same context always produces the
        same prompt, which section 5 of the AI Rules requires.
        """
        blocks: list[str] = []

        if package.user:
            user = package.user
            lines = [f"Name: {user.name}"]
            if user.goal:
                lines.append(f"Goal: {user.goal}")
            if user.fitness_level:
                lines.append(f"Fitness level: {user.fitness_level}")
            if user.workout_duration_minutes:
                lines.append(f"Time available: {user.workout_duration_minutes} minutes")
            if user.problem_areas:
                lines.append(f"Focus areas: {', '.join(user.problem_areas)}")
            blocks.append("# User\n" + "\n".join(lines))

        if package.exercise:
            exercise = package.exercise
            lines = [
                f"Name: {exercise.name}",
                f"Category: {exercise.category}",
                f"Difficulty: {exercise.difficulty}",
                f"Measured by: {exercise.exercise_type}",
            ]
            if exercise.equipment:
                lines.append(f"Equipment: {', '.join(exercise.equipment)}")
            if exercise.primary_muscles:
                lines.append(f"Primary muscles: {', '.join(exercise.primary_muscles)}")
            if exercise.secondary_muscles:
                lines.append(
                    f"Secondary muscles: {', '.join(exercise.secondary_muscles)}"
                )
            if exercise.instructions:
                steps = "\n".join(
                    f"  {index}. {step}"
                    for index, step in enumerate(exercise.instructions, start=1)
                )
                lines.append(f"Documented steps:\n{steps}")
            blocks.append("# Exercise\n" + "\n".join(lines))

        if package.workout:
            workout = package.workout
            lines = [
                f"Title: {workout.title}",
                f"Goal: {workout.goal}",
                f"Difficulty: {workout.difficulty}",
                f"Estimated duration: {workout.estimated_duration_minutes} minutes",
            ]
            if workout.exercise_names:
                lines.append(f"Exercises: {', '.join(workout.exercise_names)}")
            blocks.append("# Current Workout\n" + "\n".join(lines))

        if package.sessions:
            lines = []
            for session in package.sessions:
                detail = (
                    f"- {session.exercise_name}: {session.repetitions} reps "
                    f"in {session.duration_seconds}s"
                )
                if session.average_accuracy is not None:
                    detail += f", tracking confidence {session.average_accuracy}%"
                lines.append(detail)
                for note in session.common_feedback:
                    lines.append(f"    coaching cue recorded: {note}")
            blocks.append("# Recorded Sessions\n" + "\n".join(lines))

        if package.progress:
            progress = package.progress
            blocks.append(
                "# Progress\n"
                f"Current streak: {progress.current_streak} days\n"
                f"Longest streak: {progress.longest_streak} days\n"
                f"Workouts completed: {progress.total_workouts}\n"
                f"Total minutes trained: {progress.total_minutes}"
            )

        if package.conversation and package.conversation.messages:
            turns = "\n".join(
                f"{message.role}: {message.content}"
                for message in package.conversation.messages
            )
            blocks.append("# Recent Conversation\n" + turns)

        if package.application:
            application = package.application
            lines = [
                f"Supported exercises: {application.supported_exercise_count}",
            ]
            if application.supported_goals:
                lines.append(f"Supported goals: {', '.join(application.supported_goals)}")
            if application.capabilities:
                lines.append("Capabilities:")
                lines.extend(f"  - {item}" for item in application.capabilities)
            blocks.append("# Application\n" + "\n".join(lines))

        return "\n\n".join(blocks)


def load_prompt_templates(path: Path | None = None) -> dict:
    """Load and validate the prompt templates.

    Raises:
        PromptConstructionError: If the file is missing, unparsable, or lacks a
            template for a supported intent.
    """
    target = path or PROMPT_CONFIGURATION_FILE

    if not target.is_file():
        raise PromptConstructionError(f"Prompt templates not found: {target}")

    try:
        templates = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise PromptConstructionError("Prompt templates are not valid YAML.") from error

    if not isinstance(templates, dict) or "system_prompt" not in templates:
        raise PromptConstructionError("Prompt templates are missing the system prompt.")

    tasks = templates.get("task_prompts") or {}
    missing = sorted(str(intent) for intent in Intent if str(intent) not in tasks)
    if missing:
        raise PromptConstructionError(
            "Prompt templates are missing intents: " + ", ".join(missing)
        )

    return templates


def build_prompt_builder() -> PromptBuilder:
    """Return a builder wired to the application's prompt templates."""
    return PromptBuilder(load_prompt_templates())
