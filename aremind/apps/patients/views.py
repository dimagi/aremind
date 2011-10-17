import datetime
import json
import logging

from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.core.mail import mail_admins
from django.core.urlresolvers import reverse
from django.db.models import Count, Q
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from rapidsms.messages import OutgoingMessage
from rapidsms.models import Connection
import rapidsms.contrib.messagelog.models as messagelog
from threadless_router.router import Router

from aremind.decorators import has_perm_or_basicauth
from aremind.apps.adherence.models import (get_contact_message, PatientSurvey,
                                           PillsMissed)
from aremind.apps.adherence.types import *
from aremind.apps.patients import models as patients
from aremind.apps.patients.forms import PatientRemindersForm, PatientOnetimeMessageForm, PillHistoryForm
from aremind.apps.patients.importer import parse_payload

_ = lambda s: s

logger = logging.getLogger('aremind.apps.patients')
logger.setLevel(logging.DEBUG)

@csrf_exempt
@require_http_methods(['POST'])
@has_perm_or_basicauth('patients.add_patientdatapayload', 'Patients')
def receive_patient_record(request):
    ''' Accept data submissions from the the site via POST. '''
    if request.META['CONTENT_TYPE'] != 'text/xml':
        logger.warn('incoming post does not have text/xml content type')
        logger.debug(request)
    content = request.raw_post_data
    if not content:
        logger.error("No XML data appears to be attached.")
        return http.HttpResponseServerError("No XML data appears to be attached.")
    payload = patients.PatientDataPayload.objects.create(raw_data=content)
    try:
        parse_payload(payload)
    except Exception as e:
        mail_admins(subject="Patient Import Failed", message=unicode(e))
        return http.HttpResponseServerError(unicode(e))
    return http.HttpResponse("Data submitted succesfully.")


@login_required
def list_patients(request):
    patients_list = patients.Patient.objects.all().annotate(
        reminder_count=Count('contact__reminders', distinct=True),
        feed_count=Count('contact__feeds', distinct=True),
        message_count=Count('wisepill_messages', distinct=True),
    )
    context = {'patients': patients_list}
    return render(request, 'patients/patient_list.html', context)



@login_required
@transaction.commit_on_success
def create_edit_patient(request, patient_id=None):
    new_patient = False
    if patient_id:
        patient = get_object_or_404(patients.Patient, pk=patient_id)
    else:
        patient = patients.Patient()
        new_patient = True
    if request.method == 'POST':
        form = PatientRemindersForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            
            # If the patient was just added, send a confirmation SMS
            if new_patient:
                msg = OutgoingMessage(patient.contact.default_connection, _("Thank you for joining the study."))
                router = Router()
                success = True
                try:
                    router.outgoing(msg)
                except Exception, e:
                    logger.exception(e)
                    success = False
                if not success:
                    messages.error(request, _("An error occurred when trying to send confirmation SMS"))
            
            messages.info(request, "Patient info saved.")
            return redirect('patient-list')
    else:
        form = PatientRemindersForm(instance=patient)
    context = {'patient': patient, 'form': form}
    return render(request, 'patients/create_edit_patient.html', context)

@login_required
def messages_to_patient(request, patient_id):
    patient = get_object_or_404(patients.Patient, pk=patient_id)
    contact = patient.contact
    connections = Connection.objects.filter(contact=contact)
    messages = messagelog.Message.objects.filter(
        Q(contact=patient.contact) | Q(connection__in=connections)) \
        .order_by('-date')
    # note - can't call these 'messages' in the request context because
    # then our base template will try to render them as Django 'messages'
    context = dict(patient=patient, texts=messages)
    return render(request, 'patients/messages_to_patient.html', context)


@login_required
def patient_onetime_message(request, patient_id):
    """Send a onetime message to a patient.
    Default to getting it from their feeds but allow editing that."""

    patient = get_object_or_404(patients.Patient, pk=patient_id)
    if request.method == 'POST':
        form = PatientOnetimeMessageForm(request.POST)
        if form.is_valid():
            message = form.cleaned_data['message']
            connection = patient.contact.default_connection
            msg = OutgoingMessage(connection, message)
            router = Router()
            success = True
            try:
                router.outgoing(msg)
            except Exception, e:
                logger.exception(e)
                success = False
            if success:
                messages.success(request, "Message sent to patient %s" % patient.subject_number)
            else:
                messages.error(request, "An error occurred while trying to send the message to patient %s" % patient.subject_number)

            return redirect('patient-list')
    else:
        # Set default message
        message = get_contact_message(patient.contact)
        form = PatientOnetimeMessageForm(initial={'message': message})
    context = { 'patient': patient, 'form': form }
    return render(request, 'patients/patient_onetime_message.html', context)

@login_required
def patient_start_adherence_tree(request, patient_id):
    """Start adherence tree interaction with patient."""
    patient = get_object_or_404(patients.Patient, pk=patient_id)
    survey = PatientSurvey(patient=patient, query_type=QUERY_TYPE_SMS, is_test=True)
    survey.start_date = datetime.datetime.now()
    survey.subject_number = patient.subject_number
    survey.save()
    survey.start()
    return redirect('patient-list')

@login_required
def patient_start_ivr(request, patient_id):
    """Start interactive voice interaction with patient."""
    patient = get_object_or_404(patients.Patient, pk=patient_id)
    survey = PatientSurvey(patient=patient, query_type=QUERY_TYPE_IVR, is_test=True)
    survey.start()
    return redirect('patient-list')

@csrf_exempt
def patient_ivr_complete(request, patient_id):
    """
    We tell tropo to call us back at this view's URL with the results
    (good or bad) of running an IVR.
    """

    logger.debug("##%s" % request.raw_post_data)

    patient = get_object_or_404(patients.Patient, pk=patient_id)
    survey = PatientSurvey.find_active(patient, QUERY_TYPE_IVR)

        

    try:
        if not survey:
            logger.error("Could not find an IVR survey in progress for patient %s" % patient)
            return http.HttpResponseServerError()

        postdata = json.loads(request.raw_post_data)
        
        if 'result' in postdata:
            # Survey result
            result = postdata['result']
            logger.debug("## Results=%r" % result)
            if 'error' in result and result['error'] is not None:
                logger.error("## Error from phone survey: %s" % result['error'])
                survey.completed(PatientSurvey.STATUS_ERROR)
                return http.HttpResponse()

            if result['complete'] == False:
                survey.completed(PatientSurvey.STATUS_NO_ANSWER)
                return http.HttpResponse()
                                      
            if 'actions' not in result:
                # Some kind of error
                if result['state'] == 'DISCONNECTED':
                    # seem to get this if we hang up in the middle
                    survey.completed(PatientSurvey.STATUS_NOT_COMPLETED)
                    return http.HttpResponse()

            actions = result['actions']
            # actions can be either an array of dictionaries or a single
            # dictionary, sigh.  Figure out if it's a single dictionary
            # and wrap it in an array to avoid insanity.
            if isinstance(actions, dict):
                actions = [actions, ]
            num_questions_answered = 0
            complete = False
            error = False
            for item in actions:
                logger.debug("## action=%s", item)
                if item['name'] == 'question1' and \
                       item['disposition'] == 'SUCCESS':
                        # Got an answer, yay
                        answer = item['value']
                        num_pills = int(answer)
                        if not survey.is_test:
                            # remember result
                            PillsMissed(patient=patient,
                                        num_missed=num_pills,
                                        source=QUERY_TYPE_IVR).save()
                        complete = True
                elif item['disposition'] == 'TIMEOUT':
                    pass #incomplete = True
                else:
                    logger.debug("## Error on question %s for patient: disposition %s" % (item['name'], item['disposition']))
                    error = True
            if error:
                status = PatientSurvey.STATUS_ERROR
            elif not complete:
                status = PatientSurvey.STATUS_NOT_COMPLETED
            else:
                status = PatientSurvey.STATUS_COMPLETE
            survey.completed(status)
            return http.HttpResponse()
        # whoops
        logger.error("patient_ivr_complete called with no result data!!")
        survey.completed(PatientSurvey.STATUS_ERROR)
        return http.HttpResponseServerError()
    except Exception,e:
        logger.exception(e)
        survey.completed(PatientSurvey.STATUS_ERROR)
        return http.HttpResponseServerError()

def audio_file_url(filename):
    """Given a filename, work out the URL that tropo needs to use
    to download it from us.  Tropo apparently needs the full URL,
    at least otherwise it reads out the filename instead of
    downloading and playing it :-(
    We're going to end up with something like
    http://example.com:8000/static/audio/01-Intro.mp3
    """
    root = settings.STATIC_URL  # ends in '/'
    use_ssl = getattr(settings, 'USE_SSL_FOR_AUDIO_FILE_URLS', False)
    alt_domain = getattr(settings, 'IVR_AUDIO_DOMAIN_URL', False) #an unfortunate tropo necessary hack.
    scheme = "https" if use_ssl else "http"
    url = "%s://%s%saudio/%s" % (scheme, Site.objects.get_current().domain, root, filename)
    if(alt_domain):
        url = "http://%s%saudio/%s" % (alt_domain, root, filename)
    logging.info("##AUDIO_URL=%s" % url)
    return url

# Maybe this should be a setting
USE_RECORDED_VOICE = True

@csrf_exempt
def patient_ivr_callback(request, patient_id):
    """
    When we start a patient IVR interaction, we tell the tropo
    backend to call us back at this function when tropo makes a
    http call to us about it.  The data we pass is the patient_id.
    """
    
    patient = get_object_or_404(patients.Patient, pk=patient_id)

    # Got POST from Tropo wanting to know what to do
    try:
        logger.debug("##%s" % request.raw_post_data)
        postdata = json.loads(request.raw_post_data)
        
        if 'result' in postdata:
            # Survey result
            result = postdata['result']
            logger.debug("## Results=%r" % result)
            if 'error' in result and result['error'] is not None:
                logger.error("## Error from phone survey: %s" % result['error'])
            actions = result['actions']
            for item in actions:
                if item['name'].startswith('question'):
                    if item['disposition'] == 'SUCCESS':
                        # Got an answer, yay
                        # last char is a digit with question #
                        question_num = int(item['name'][-1])
                        # date would be today minus that many days
                        date = datetime.date.today()
                        date -= datetime.timedelta(days=question_num)
                        answer = item['value']
                        num_pills = int(answer)
                        # remember result
                        patients.remember_patient_pills_taken(patient, date,
                                                              num_pills, "IVR")
                    else:
                        logger.debug("## Error on question %s for patient: disposition %s" % (item['name'],item['disposition']))

            return http.HttpResponse()

        # New call, tell Tropo to run the survey
        our_callback_url = reverse('patient-ivr-complete', kwargs={'patient_id':patient_id})

        session = postdata['session']
        # Tell Tropo to call, ask questions, hang up

        # Need to tell Tropo explicitly that we want results back
        on1 = { 'on': {
            "next": our_callback_url,
            "event":"continue"}}
        on2 = { 'on': {
            "next": our_callback_url,
            "event":"error"}}
        on3 = { 'on': {
            "next": our_callback_url,
            "event":"hangup"}}
        on4 = { 'on': {
            "next": our_callback_url,
            "event":"incomplete"}}
        call = { 'call': {
            'to': patient.contact.default_connection.identity,
            'channel': 'VOICE',
            'name': patient_id,  # so we can correlate later
            }}

        if USE_RECORDED_VOICE:
            welcome_value = audio_file_url('01-Intro.mp3')
            ask_value = audio_file_url('02-HowManyDoses.mp3')
            thankyou_values = (audio_file_url('03-ThankYou.mp3'),
                              audio_file_url('04-YourAdherenceScoreIs.mp3'),
                              (u"%d" % patient.adherence()))
        else:
            welcome_value = "This is ARemind calling to see how you're doing."
            ask_value = 'How many pills did you miss in the last four days?  Please enter the number, then press pound.'
            thankyou_values = ("Thank you.  Your adherence is %d percent." % patient.adherence(),)

        # if call works, talk to them
        commands = [ on1, on2, on3, on4, call ]
        commands.append({ 'say': {
            'value': welcome_value,
            }})
        commands.append({ 'ask': {
            'say': { 'value': ask_value,
                     },
            'choices': { 'value': '[1-3 DIGITS]',
                         'mode': 'dtmf',
                         'terminator': '#'},
            'attempts': 3,
            'name': 'question1',
            }})
        for val in thankyou_values:
            commands.append({ 'say': {
            'value': val,
            }})
        commands.append({ 'hangup': None })

        to_return = { 'tropo': commands }
        logger.info("##Returning %s" % to_return)
        return http.HttpResponse(json.dumps(to_return))
    except Exception,e:
        logger.exception(e)
        return http.HttpResponseServerError()
        
@login_required
def patient_pill_report(request, patient_id):
    patient = get_object_or_404(patients.Patient, pk=patient_id)
    pills = patients.PatientPillsTaken.objects.filter(patient=patient).order_by('-date')
    context = {'patient': patient, 'pills': pills}
    return render(request, 'patients/patient_pill_report.html', context)


@login_required
def create_edit_pill_history(request, patient_id, pill_id=None):
    if pill_id:
        pill = get_object_or_404(patients.PatientPillsTaken, pk=pill_id, patient=patient_id)
        patient = pill.patient
    else:
        patient = get_object_or_404(patients.Patient, pk=patient_id)
        pill = patients.PatientPillsTaken(patient=patient)
    if request.method == 'POST':
        form = PillHistoryForm(request.POST, instance=pill)
        if form.is_valid():
            pill = form.save()
            messages.success(request, "Pill history saved.")
            return redirect('patient-report', patient_id)
    else:
        form = PillHistoryForm(instance=pill)
    context = {'patient': patient, 'pill': pill, 'form': form}
    return render(request, 'patients/create_edit_pill_history.html', context)
