from celery.task import Task
from celery.registry import tasks

from threadless_router.router import Router

from aremind.apps.adherence.models import Feed
from aremind.apps.adherence.app import send_fhi_report_email


class ReminderSchedulerTask(Task):
    def run(self):
        router = Router()
        app = router.get_app("aremind.apps.adherence")
        app.cronjob()


tasks.register(ReminderSchedulerTask)


class FeedUpdatesTask(Task):
    def run(self):
        return Feed.objects.fetch_feeds()
        

tasks.register(FeedUpdatesTask)

"""
This task is invoked to send the daily csv report.
"""
class FHIEmailReportTask(Task):
    def run(self):
        send_fhi_report_email()

tasks.register(FHIEmailReportTask)
