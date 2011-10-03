# Code related to using decisiontree to survey using SMS

import datetime
import logging
import re

from django.dispatch import receiver
from decisiontree.models import Question, Answer, Tree, TreeState, Transition
from threadless_router.base import incoming
from threadless_router.router import Router
from rapidsms.messages import OutgoingMessage
import aremind.apps.adherence.models
from aremind.apps.adherence.types import *
from aremind.apps.patients.models import Patient, remember_patient_pills_taken

logger = logging.getLogger('adherence.sms')

TRIGGER = "start tree"
ANSWER_RE = r".*(\d+).*"

"""UW Implementation - additional constants"""
DAYS_FOR_MONTHLY_QUESTIONS = [1, 30, 60]
LAST_DAILY_TREESTATE = "ask_daily_question4"
FINAL_SURVEY_DAY = 60


# In RapidSMS, message translation is done in OutgoingMessage, so no need
# to attempt the real translation here.  Use _ so that ./manage.py makemessages
# finds our text.
_ = lambda s: s

def get_tree():
    """
    UW Implementation
    Returns the Tree object used to perform the study survey. This tree is created in
    the database at installation time from the initial_data.json fixture in the adherence app.
    """
    return Tree.objects.get(trigger = TRIGGER)

def start_tree_for_patient(tree, patient):
    """Trigger tree for a given patient.
    Will result in our sending them the first question in the tree."""

    connection = patient.contact.default_connection

    # if one is in progress, end it
    Router().get_app('decisiontree').end_sessions(connection)

    # fake an incoming message from our patient that triggers the tree

    backend_name = connection.backend.name
    address = connection.identity
    incoming(backend_name, address, tree.trigger)

def start_tree_for_all_patients():
    logging.debug("start_tree_for_all_patients")
    tree = get_tree()
    for patient in Patient.objects.all():
        start_tree_for_patient(tree, patient)


"""
UW Kenya Implementation

Upon startup of the adherence app, this function is registered with the 
decisiontree app using function set_session_listener().

This function is called at the beginning and end of every decisiontree 
session. When a session is starting up, we check to see if it's the last 
day of the study and deactivate the query schedule if so.

When a session in ending, we do the following:
    If it was a daily survey that completed, we need to check 
    to see if it's one of the days where we need to ask the
    monthly questions.

    If it was the monthly survey that completed, we can let
    the session end.
"""
def session_listener(session, is_ending):
    # Lookup the patient and calculate number of days since enrollment
    connection = session.connection
    patient = Patient.objects.get(contact = connection.contact)
    days_since_enrollment = patient.get_days_since_enrollment(session.start_date.date())
    
    if is_ending:
        
        # Ensure that the current session ended gracefully and that the appropriate number of days have passed to ask monthly questions
        if not session.canceled and days_since_enrollment in DAYS_FOR_MONTHLY_QUESTIONS:
            
            # If the last tree state asked the final daily question, then it's a daily session that just finished, so ask the monthly questions.
            # Otherwise, it's a monthly session that just finished, so just let the session end.
            entries = session.entries
            last_state_name = entries.order_by("-time")[0].transition.current_state.name
            if last_state_name == LAST_DAILY_TREESTATE:
                next_state = TreeState.objects.get(name = "ask_monthly_question1")
                session.state = next_state
                session.canceled = None
                session.save()
    else:
        
        # If it's the last day of the survey, deactivate the query schedule so that it won't start again after this day
        if days_since_enrollment >= FINAL_SURVEY_DAY:
            query_schedule = patient.adherence_query_schedules.all()[0]
            query_schedule.active = False
            query_schedule.save()

