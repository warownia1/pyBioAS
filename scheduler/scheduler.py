import logging
import threading
import time

from sqlalchemy.orm import joinedload

import settings
from db import start_session
from db.models import Request, Result
from .command.command_factory import CommandFactory
from .task_queue import queue_run
from .task_queue.job import JobStatus


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s %(name)s %(levelname)s: %(message)s",
    "%d %b %H:%M:%S"
)
handler.setFormatter(formatter)
logger.addHandler(handler)


class Scheduler:

    def __init__(self):
        self._shutdown = False
        self._tasks = set()
        self._tasks_lock = threading.Lock()
        self._command_class = {
            service: CommandFactory.get_local_command_class(service)
            for service in settings.SERVICES
        }

    def database_poll_loop(self):
        print("Scheduler starts watching database.")
        while not self._shutdown:
            with start_session() as session:
                self._poll_database(session)
            time.sleep(5)

    def _poll_database(self, session):
        logger.debug("poll db")
        pending_requests = (session.query(Request).
                            options(joinedload('options')).
                            filter(Request.status == Request.STATUS_PENDING).
                            all())
        logger.debug("found {} requests".format(len(pending_requests)))
        for request in pending_requests:
            self.queue_task(request)
            session.commit()

    def queue_task(self, request):
        command_cls = self._command_class[request.service]
        options = {
            option.name: option.value
            for option in request.options
        }
        command = command_cls(options)
        with self._tasks_lock:
            deferred_result = queue_run(command)
            self._tasks.add(Task(deferred_result, request))
            request.status = request.STATUS_QUEUED

    def collector_loop(self):
        print("Scheduler starts collecting tasks from worker.")
        while not self._shutdown:
            with start_session() as session:
                for task in self._collect_finished():
                    session.query(Request). \
                            filter(Request.id == task.request_id). \
                            update({"status": Request.STATUS_COMPLETED})
                    result = task.deferred_result.result.result
                    res = Result(
                        return_code=result.retcode,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        request_id=task.request_id
                    )
                    session.add(res)
                session.commit()
            time.sleep(5)

    def _collect_finished(self):
        """
        Browses all running tasks and collects those which are finished.
        They are removed from the `tasks` set.
        :return: set of finished tasks
        :rtype: set(Task)
        """
        logger.debug("collecting finished tasks")
        finished = set()
        with self._tasks_lock:
            for task in self._tasks:
                status = task.deferred_result.status
                if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    finished.add(task)
            self._tasks = self._tasks.difference(finished)
        logger.debug("found {} tasks".format(len(finished)))
        return finished

    def shutdown(self):
        self._shutdown = True


class Task:
    __slots__ = ["deferred_result", "request_id"]

    def __init__(self, deferred_result, request):
        self.deferred_result = deferred_result
        self.request_id = request.id


def start_scheduler():
    scheduler = Scheduler()
    collector_thread = threading.Thread(
        target=scheduler.collector_loop,
        name="CollectorThread"
    )
    collector_thread.start()
    poll_thread = threading.Thread(
        target=scheduler.database_poll_loop,
        name="PollThread"
    )
    poll_thread.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("received shutdown signal")
        scheduler.shutdown()
    print("Waiting for threads to join.")
    collector_thread.join()
    poll_thread.join()
