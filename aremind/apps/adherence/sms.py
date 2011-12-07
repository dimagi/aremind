# Code related to using decisiontree to survey using SMS

import datetime
import logging
import re

from django.dispatch import receiver
from decisiontree.models import Question, Answer, Tree, TreeState, Transition, Entry
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

Retrieves the text associated with the decisiontree entry for the
given session and state name. If the entry does not exist, None
is returned.
"""
def get_decisiontree_entry_text(session, state_name):
    try:
        entry = Entry.objects.filter(session = session).get(transition__current_state__name = state_name)
        return entry.text
    except Entry.DoesNotExist:
        return None

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
    
    # Lookup survey and set survey constants
    survey = aremind.apps.adherence.models.PatientSurvey.find_active(patient, QUERY_TYPE_SMS)
    completed = aremind.apps.adherence.models.PatientSurvey.STATUS_COMPLETE
    not_completed = aremind.apps.adherence.models.PatientSurvey.STATUS_NOT_COMPLETED
    
    # Variable to check whether to send survey completion message
    send_survey_completion_message = False
    
    if is_ending:
        survey.subject_number = patient.subject_number
        survey.phone = connection.contact.phone
        survey.language = connection.contact.language
        survey.mobile_network = connection.contact.mobile_network
        survey.ask_password_response = get_decisiontree_entry_text(session, "ask_password")
        survey.daily_question1_response = get_decisiontree_entry_text(session, "ask_daily_question1")
        survey.daily_question2_response = get_decisiontree_entry_text(session, "ask_daily_question2")
        survey.daily_question3_response = get_decisiontree_entry_text(session, "ask_daily_question3")
        survey.daily_question4_response = get_decisiontree_entry_text(session, "ask_daily_question4")
        survey.monthly_question1_response = get_decisiontree_entry_text(session, "ask_monthly_question1")
        survey.monthly_question2_response = get_decisiontree_entry_text(session, "ask_monthly_question2")
        
        count = (0 if survey.ask_password_response is None else 1)
        count += (0 if survey.daily_question1_response is None else 1)
        count += (0 if survey.daily_question2_response is None else 1)
        count += (0 if survey.daily_question3_response is None else 1)
        count += (0 if survey.daily_question4_response is None else 1)
        count += (0 if survey.monthly_question1_response is None else 1)
        count += (0 if survey.monthly_question2_response is None else 1)
        survey.questions_answered = count
        
        survey.save()
        
        if session.canceled:
            survey.completed(not_completed)
        else:
            if (days_since_enrollment in DAYS_FOR_MONTHLY_QUESTIONS) or survey.is_test:
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
                    # It's a monthly survey that completed successfully
                    survey.completed(completed)
                    send_survey_completion_message = True
            else:
                # It's a daily survey that completed successfully
                survey.completed(completed)
                send_survey_completion_message = True
            
            if send_survey_completion_message:
                msg = OutgoingMessage(connection, _("Thank you. Please remember to delete these messages."))
                router = Router()
                router.outgoing(msg)


