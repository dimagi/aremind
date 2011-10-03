from celery.task import Task
from celery.registry import tasks

from threadless_router.router import Router

from aremind.apps.adherence.models import Feed

from decisiontree.models import Session

from django.conf import settings

import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


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
UW Kenya Implementation

This task is invoked periodically to see if any decisiontree sessions have 
states whose questions must be asked again.
"""
class DecisionTreeTimeoutTask(Task):
    def run(self):
        logger.critical("Entering DecisionTreeTimeoutTask...")
        router = Router()
        app = router.get_app("decisiontree")
        for session in Session.objects.filter(
            canceled__isnull=True
           ,state__name__in = settings.DECISIONTREE_TIMEOUT_STATES
           ,num_tries__lt = settings.DECISIONTREE_TIMEOUT_MAX_RETRIES):
            app.tick(session)
        logger.critical("Exiting DecisionTreeTimeoutTask...")


tasks.register(DecisionTreeTimeoutTask)
