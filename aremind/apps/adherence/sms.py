# Code related to using decisiontree to survey using SMS

import datetime
import logging
import re

from django.dispatch import receiver
from decisiontree.app import session_end_signal
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

# In RapidSMS, message translation is done in OutgoingMessage, so no need
# to attempt the real translation here.  Use _ so that ./manage.py makemessages
# finds our text.
_ = lambda s: s

def get_tree():
    """Create or retrieve a decisiontree Tree in the database.
    Returns the Tree object."""
    
    try:
        return Tree.objects.get(trigger = TRIGGER)
    except Tree.DoesNotExist:
        pass # we'll create it below

    q1_text = _("How many pills did you miss in the last four days?")
    err_text = _("Sorry, please respond with a number. ")

    q1, x = Question.objects.get_or_create(text = q1_text,
                                           error_response = err_text + q1_text)
    state1,x = TreeState.objects.get_or_create(name = "state1",
                                             question = q1,
                                             num_retries = 3)

    answer,x = Answer.objects.get_or_create(name="numberofpills",
                                          type='R',
                                          answer=ANSWER_RE)

    trans1,x = Transition.objects.get_or_create(current_state=state1,
                                              answer=answer,
                                              next_state=None) # end

    # We only use this internally, so not translated
    # Receipt of this message triggers starting the tree.
    trigger = TRIGGER

    # Tree has a uniqueness constraint on the trigger
    tree,x = Tree.objects.get_or_create(trigger = trigger.lower(),
                                        defaults={'root_state': state1})

    tree.root_state = state1
    tree.completion_text = ''
    tree.save()

    return tree

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
    for patient in Patient.objects.filter(disabled=False):
        start_tree_for_patient(tree, patient)

# When we complete an adherence survey, update adherence.pillsmissed
@receiver(session_end_signal)
def session_end(sender, **kwargs):
    session = kwargs['session']
    canceled = kwargs['canceled']
    message = kwargs['message']

    # for convenience
    PatientSurvey = aremind.apps.adherence.models.PatientSurvey

    # find the patient
    connection = session.connection
    try:
        patient = Patient.objects.get(contact = connection.contact)
        if patient.disabled:
            return #Skip patients that are disabled on the system
    except Patient.DoesNotExist:
        # No patient, this session might not be relevant to this app
        return

    survey = PatientSurvey.find_active(patient, QUERY_TYPE_SMS)

    if not survey:
        return

    if canceled:
        survey.completed(PatientSurvey.STATUS_NOT_COMPLETED)
        return

    tree = session.tree
    entries = session.entries

    if entries.count() < 1:
        survey.completed(PatientSurvey.STATUS_NOT_COMPLETED)
        return

    entry = entries.all()[0]
    # Pick the relevant part of the answer
    text = re.match(ANSWER_RE, entry.text).group(1)
    num_pills = int(text)
    if not survey.is_test:
        aremind.apps.adherence.models.PillsMissed(patient=patient,
                                                  num_missed=num_pills,
                                                  source=QUERY_TYPE_SMS).save()
    survey.completed(PatientSurvey.STATUS_COMPLETE)

    # After completing survey, tell patient what their current adherence is
    connection = patient.contact.default_connection
    adherence = patient.adherence()  # integer percentage
    response_text = _("Thank you. Your adherence is %(adherence)s%%, as measured by the black study pillbox.")
    kwargs = dict(adherence=adherence)
    if message:
        message.respond(response_text, **kwargs)
    else:
        msg = OutgoingMessage(connection,
                              response_text, **kwargs)
        router = Router()
        router.outgoing(msg)
