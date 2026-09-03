from scheduler import BoundedScheduler, CircuitBreaker, LeaseRegistry, RetryBudget, deterministic_task_id


def test_task_id_is_deterministic_and_opaque():
    assert deterministic_task_id("job", "0") == deterministic_task_id("job", "0")
    assert "job" not in deterministic_task_id("job", "0")


def test_scheduler_deduplicates_and_honors_priority():
    seen = []
    scheduler = BoundedScheduler(max_workers=1, max_queue=4)
    assert scheduler.submit("low", lambda: seen.append("low"), priority=20)
    assert scheduler.submit("high", lambda: seen.append("high"), priority=1)
    assert not scheduler.submit("high", lambda: seen.append("duplicate"), priority=1)
    scheduler.run()
    assert seen == ["high", "low"]


def test_retry_budget_is_bounded():
    budget = RetryBudget(max_attempts=2)
    assert budget.allow("t")
    assert budget.allow("t")
    assert not budget.allow("t")
    assert budget.attempts("t") == 2


def test_circuit_breaker_opens_and_recovers():
    breaker = CircuitBreaker(threshold=2, cooldown=10)
    breaker.failure(now=1)
    assert breaker.allow(now=1)
    breaker.failure(now=2)
    assert not breaker.allow(now=5)
    assert breaker.allow(now=12)
    breaker.success()
    assert breaker.allow(now=13)


def test_lease_heartbeat_and_expiry():
    leases = LeaseRegistry(lease_seconds=10)
    lease = leases.acquire("t", "w", now=100)
    assert lease.worker_id == "w"
    leases.heartbeat("t", "w", now=105)
    assert leases.expired_tasks(now=114) == []
    assert leases.expired_tasks(now=115) == ["t"]
    leases.acquire("t", "w2", now=115)
    leases.release("t", "w2")
    assert leases.expired_tasks(now=116) == []


def test_scheduler_shutdown_rejects_new_tasks():
    scheduler = BoundedScheduler()
    scheduler.shutdown()
    try:
        scheduler.submit("t", lambda: None)
    except RuntimeError as exc:
        assert "stopping" in str(exc)
    else:
        raise AssertionError("shutdown scheduler accepted a task")
