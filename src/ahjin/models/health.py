"""ModelHealthTracker — In-memory runtime health signals and circuit breakers.

Health is operational state, not intelligence quality.
Health is observed from real traffic:
- failures → degrade
- repeated failures → unhealthy + cooldown
- cooldown expiry → model becomes eligible for a recovery PROBE
- successful invocation → health confirmed restored (evidence-based)

No permanent blacklist.
No background polling.
Thread-safe state updates via threading.Lock.
"""

import threading
import time
from enum import Enum

import structlog

logger = structlog.get_logger()

# Failure thresholds
_DEGRADED_THRESHOLD = 1   # consecutive failures before DEGRADED
_UNHEALTHY_THRESHOLD = 3  # consecutive failures before UNHEALTHY


class ModelHealthStatus(str, Enum):
    """Health status classification."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class ModelHealthState:
    """Runtime health metrics for a single model.

    Thread-safe: all mutations and reads of mutable fields are protected by a Lock.
    """

    def __init__(self, cooldown_seconds: float = 60.0) -> None:
        self._lock = threading.Lock()
        self.cooldown_seconds: float = cooldown_seconds

        # Mutable fields — always access under _lock
        self.status: ModelHealthStatus = ModelHealthStatus.HEALTHY
        self.consecutive_failures: int = 0
        self.ema_latency_ms: float = 0.0
        self.last_failure_time: float | None = None

    def is_available(self) -> bool:
        """Return True if this model is eligible for selection.

        HEALTHY → always eligible.
        DEGRADED → eligible (health has degraded but not critically).
        UNHEALTHY + cooldown expired → eligible for a recovery probe.
           NOTE: we do NOT auto-restore status here. Status is only
           restored to HEALTHY upon a successful invocation (evidence-based).
        UNHEALTHY + cooldown not expired → not eligible.
        """
        with self._lock:
            if self.status in (ModelHealthStatus.HEALTHY, ModelHealthStatus.DEGRADED):
                return True
            # UNHEALTHY: check cooldown
            if self.last_failure_time is not None:
                elapsed = time.monotonic() - self.last_failure_time
                if elapsed > self.cooldown_seconds:
                    # Cooldown expired → allow a recovery probe attempt.
                    # Do NOT reset status yet; status is restored only on record_success.
                    return True
            return False

    def record_success(self, latency_ms: float) -> None:
        """Record successful invocation.

        Resets consecutive failures and restores HEALTHY status.
        This is the ONLY way a model recovers — evidence-based.
        """
        with self._lock:
            self.consecutive_failures = 0
            self.status = ModelHealthStatus.HEALTHY
            if self.ema_latency_ms == 0.0:
                self.ema_latency_ms = latency_ms
            else:
                # Exponential Moving Average (alpha=0.3)
                self.ema_latency_ms = 0.3 * latency_ms + 0.7 * self.ema_latency_ms

    def record_failure(self) -> None:
        """Record invocation failure and update circuit breaker state."""
        with self._lock:
            self.consecutive_failures += 1
            self.last_failure_time = time.monotonic()
            if self.consecutive_failures >= _UNHEALTHY_THRESHOLD:
                self.status = ModelHealthStatus.UNHEALTHY
            else:
                self.status = ModelHealthStatus.DEGRADED

    # --- Read-only snapshots for external consumers (no lock required for Enum/float) ---

    @property
    def snapshot_status(self) -> ModelHealthStatus:
        with self._lock:
            return self.status

    @property
    def snapshot_consecutive_failures(self) -> int:
        with self._lock:
            return self.consecutive_failures

    @property
    def snapshot_ema_latency_ms(self) -> float:
        with self._lock:
            return self.ema_latency_ms


class ModelHealthTracker:
    """In-memory tracker managing health state for all models.

    The _states dict is accessed under a single dict-level lock to
    prevent races during lazy initialization.
    """

    def __init__(self) -> None:
        self._states: dict[str, ModelHealthState] = {}
        self._registry_lock = threading.Lock()

    def get_state(self, model_id: str) -> ModelHealthState:
        """Get or initialize health state for a model."""
        with self._registry_lock:
            if model_id not in self._states:
                self._states[model_id] = ModelHealthState()
            return self._states[model_id]

    def record_success(self, model_id: str, latency_ms: float) -> None:
        """Record successful invocation and restore health if needed."""
        state = self.get_state(model_id)
        prev_status = state.snapshot_status
        state.record_success(latency_ms)
        if prev_status != ModelHealthStatus.HEALTHY:
            logger.info(
                "Model health restored to HEALTHY after successful invocation",
                model_id=model_id,
                latency_ms=round(latency_ms, 1),
            )

    def record_failure(self, model_id: str) -> None:
        """Record invocation failure."""
        state = self.get_state(model_id)
        state.record_failure()
        logger.warning(
            "Model failure recorded",
            model_id=model_id,
            consecutive_failures=state.snapshot_consecutive_failures,
            status=state.snapshot_status.value,
        )
