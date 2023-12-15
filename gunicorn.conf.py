# gunicorn_config.py

from libs import logger


def worker_exit(server: object, worker: object) -> None:
    """
    Perform cleanup tasks when a worker process exits.

    Args:
        server (object): The Gunicorn server instance.
        worker (object): The worker process that is exiting.

    Returns:
        None
    """
    logger.info(f"Performing cleanup tasks for worker (pid: {worker.pid})")

    if hasattr(worker.app.callable, "observer"):
        logger.info("Stopping observer thread")
        worker.app.callable.observer.stop()
        worker.app.callable.observer.join()

    if hasattr(worker.app.callable, "executor"):
        logger.info("Shutting down executor")
        worker.app.callable.executor.shutdown(wait=True)


def post_fork(server: object, worker: object) -> None:  # pylint: disable=unused-argument
    """
    This function is called after a worker process has been forked.

    Args:
        server (object): The Gunicorn server instance.
        worker (object): The worker process that has been forked.
    """
    pass  # pylint: disable=unnecessary-pass


def on_starting(server: object) -> None:  # pylint: disable=unused-argument
    """
    Function called before the master process is initialized.

    Args:
        server (object): The Gunicorn server instance.

    Returns:
        None
    """
    pass  # pylint: disable=unnecessary-pass
