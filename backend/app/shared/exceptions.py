# file_name: exceptions.py

"""Application-wide exception hierarchy.

Every exception carries the documented API error code and HTTP status defined in
``contracts/common/01_ERROR_CODES.md``. Translating an exception into an HTTP
response is the responsibility of the API layer, so nothing here imports FastAPI.
"""


class GymVisionError(Exception):
    """Base class for every error raised by GymVision AI.

    Subclasses declare the documented error code and HTTP status so the API layer
    can serialise them without knowing which module raised the error.
    """

    error_code: str = "SYSTEM-001"
    http_status: int = 500
    default_message: str = "Internal server error."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)

    def to_dict(self) -> dict[str, str]:
        """Return the error payload described in COMMON-001 section 2."""
        return {"code": self.error_code, "message": self.message}


class UnsupportedExerciseError(GymVisionError):
    """Raised when an exercise identifier has no registered detector."""

    error_code = "EXERCISE-005"
    http_status = 400
    default_message = "Unsupported exercise."


class DetectorUnavailableError(GymVisionError):
    """Raised when a registered detector cannot be instantiated or executed."""

    error_code = "EXERCISE-006"
    http_status = 503
    default_message = "Exercise detector unavailable."


class ExerciseNotFoundError(GymVisionError):
    """Raised when no exercise matches the requested identifier or slug."""

    error_code = "EXERCISE-001"
    http_status = 404
    default_message = "Exercise not found."


class ExerciseConfigurationError(GymVisionError):
    """Raised when an exercise configuration file is missing or invalid.

    Configuration is validated during startup, so this error prevents the
    application from starting rather than failing a request. See
    ``docs/01_foundation/10_CONFIGURATION_ARCHITECTURE.md`` principle CFG-005.
    """

    error_code = "SYSTEM-001"
    http_status = 500
    default_message = "Exercise configuration is invalid."


class DatabaseUnavailableError(GymVisionError):
    """Raised when the database is not configured or cannot be reached."""

    error_code = "SYSTEM-002"
    http_status = 503
    default_message = "Database unavailable."


class AuthenticationError(GymVisionError):
    """Raised when a request carries no usable credentials."""

    error_code = "AUTH-001"
    http_status = 401
    default_message = "Authentication required."


class AuthenticationUnavailableError(GymVisionError):
    """Raised when the backend cannot verify credentials at all.

    Distinct from a rejected token: nothing is wrong with the request, the
    capability is not configured. The message stays generic so a client learns
    nothing about the deployment, per
    ``docs/09_security/47_SECURITY_ARCHITECTURE.md`` section 19.
    """

    error_code = "SYSTEM-003"
    http_status = 503
    default_message = "Service temporarily unavailable."


class InvalidTokenError(GymVisionError):
    """Raised when an access token is malformed or fails signature checks."""

    error_code = "AUTH-002"
    http_status = 401
    default_message = "Invalid authentication token."


class ExpiredTokenError(GymVisionError):
    """Raised when an access token has passed its expiry."""

    error_code = "AUTH-003"
    http_status = 401
    default_message = "Authentication token expired."


class GoogleAuthenticationError(GymVisionError):
    """Raised when Google rejects or cannot verify an identity token."""

    error_code = "AUTH-004"
    http_status = 401
    default_message = "Google authentication failed."


class UserNotFoundError(GymVisionError):
    """Raised when no user matches the requested identifier."""

    error_code = "USER-001"
    http_status = 404
    default_message = "User not found."


class ProfileNotFoundError(GymVisionError):
    """Raised when a user has not yet created a body profile."""

    error_code = "USER-002"
    http_status = 404
    default_message = "Profile not found."


class WorkoutNotFoundError(GymVisionError):
    """Raised when no workout matches the requested identifier."""

    error_code = "WORKOUT-001"
    http_status = 404
    default_message = "Workout not found."


class ExerciseSessionNotFoundError(GymVisionError):
    """Raised when no exercise session matches the requested identifier."""

    error_code = "EXERCISE-002"
    http_status = 404
    default_message = "Exercise session not found."


class SessionAlreadyActiveError(GymVisionError):
    """Raised when a user starts a session while one is already running."""

    error_code = "EXERCISE-003"
    http_status = 409
    default_message = "Exercise session already active."


class AIProviderError(GymVisionError):
    """Raised when the language model provider cannot be reached or refuses."""

    error_code = "AI-001"
    http_status = 503
    default_message = "The AI assistant is temporarily unavailable."


class AITimeoutError(GymVisionError):
    """Raised when the provider does not answer within the configured timeout."""

    error_code = "AI-002"
    http_status = 503
    default_message = "The AI assistant took too long to respond."


class AIResponseError(GymVisionError):
    """Raised when a response fails validation or the safety guardrails."""

    error_code = "AI-003"
    http_status = 500
    default_message = "The AI assistant could not produce a usable response."


class PromptConstructionError(GymVisionError):
    """Raised when a prompt cannot be assembled or fails validation.

    ``AI-004`` covers context generation failure, the closest documented code.
    The message never reveals prompt internals, per
    ``instructions/04_AI_RULES.md`` section 11.
    """

    error_code = "AI-004"
    http_status = 500
    default_message = "The AI assistant could not prepare this request."


class NutritionConfigurationError(GymVisionError):
    """Raised when a food or meal template configuration is missing or invalid."""

    error_code = "SYSTEM-001"
    http_status = 500
    default_message = "Nutrition configuration is invalid."


class DietGenerationError(GymVisionError):
    """Raised when a diet plan cannot be produced.

    No partial diet plan is ever returned, per
    ``docs/03_business/23_DIET_PLANNING_ENGINE.md`` section 12.

    ``contracts/common/01_ERROR_CODES.md`` defines no diet-specific codes,
    because no diet API contract exists yet, so the generic system code is used.
    """

    error_code = "SYSTEM-001"
    http_status = 500
    default_message = "Diet plan generation failed."


class FoodNotFoundError(GymVisionError):
    """Raised when no food matches the requested identifier or slug."""

    error_code = "SYSTEM-001"
    http_status = 500
    default_message = "Food not found."


class InvalidSessionStateError(GymVisionError):
    """Raised when an operation is not legal in the session's current state."""

    error_code = "EXERCISE-004"
    http_status = 409
    default_message = "Invalid exercise state."


class SessionNotActiveError(GymVisionError):
    """Raised when progress is reported for a session that has finished."""

    error_code = "WORKOUT-004"
    http_status = 409
    default_message = "Workout session not active."


class WorkoutGenerationError(GymVisionError):
    """Raised when a workout plan cannot be produced.

    No partial workout is ever returned, per
    ``docs/03_business/20_WORKOUT_ENGINE.md`` section 13.
    """

    error_code = "WORKOUT-002"
    http_status = 500
    default_message = "Workout generation failed."


class WorkoutConfigurationError(GymVisionError):
    """Raised when a workout template file is missing or invalid."""

    error_code = "SYSTEM-001"
    http_status = 500
    default_message = "Workout configuration is invalid."


class InvalidLandmarksError(GymVisionError):
    """Raised when a frame does not carry a usable set of pose landmarks."""

    error_code = "VALIDATION-003"
    http_status = 422
    default_message = "Invalid field value."


class DietPlanNotFoundError(GymVisionError):
    """Raised when no diet plan matches the request.

    Also raised for a plan belonging to another user, so the response does not
    confirm that it exists. ``contracts/diet/04_GET_DIET_PLAN.md`` section 6.
    """

    error_code = "DIET-001"
    http_status = 404
    default_message = "Diet plan not found."


class DietPlanGenerationError(GymVisionError):
    """Raised when no diet plan can be produced.

    No partial plan is ever returned: half a day's meals is not a usable
    recommendation.
    """

    error_code = "DIET-002"
    http_status = 500
    default_message = "Diet plan generation failed."


class FoodLibraryUnavailableError(GymVisionError):
    """Raised when the food catalog is empty or cannot be read."""

    error_code = "DIET-003"
    http_status = 503
    default_message = "The food library is unavailable."
