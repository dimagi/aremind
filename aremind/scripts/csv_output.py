import os
from rapidsms.contrib.messagelog.models import Message
from apps.adherence.models import Reminder
from apps.adherence.models import SendReminder
from apps.adherence.models import Feed
from apps.adherence.models import Entry
from apps.adherence.models import PatientSurvey
from apps.adherence.models import PillsMissed
from apps.adherence.models import QuerySchedule
from apps.adherence.models import EntrySeen,Entry
from apps.reminders.models import Notification
from apps.reminders.models import SentNotification
from apps.wisepill.models import WisepillMessage
from decisiontree.models import Entry as DecisionTreeEntry
from decisiontree.models import Session
import csv

def pillsmissed_output(writer):
    header = ['patient', 'date', 'item_type', 
	'num_missed','source']
    writer.writerow(header)
    for pm  in PillsMissed.objects.all():
        row = []
        row.append(pm.patient.subject_number)
        row.append(pm.date.isoformat())
        row.append("PillsMissed")
        row.append(pm.num_missed)
        row.append(pm.get_source_display)
        writer.writerow(row)



def surveys_output(writer):
    header = ['patient', 'last_modified', 'item_type', 
	'query_type','is_test']
    writer.writerow(header)
    for ps  in PatientSurvey.objects.all():
        row = []
        row.append(ps.patient.subject_number)
        row.append(ps.last_modified.isoformat())
        row.append("PatientSurvey")
        row.append(ps.get_query_type_display())
        row.append(ps.is_test)
        writer.writerow(row)


def reminder_output(writer):
    header = ['patient', 'date_sent', 'item_type', 
	'reminder_id', 'reminder_str', 'status', 'date_queued', 'date_to_send', 'message', ]
    writer.writerow(header)
    for sr in SendReminder.objects.all():
        row = []
        row.append(sr.recipient.patient_set.all()[0].subject_number)
        if sr.date_sent is None:
            row.append('')
        else:
            row.append(sr.date_sent.isoformat())
        row.append('SendReminder_Sent')
        row.append(sr.reminder.id)
        row.append(str(sr.reminder))
        row.append(sr.get_status_display())
        row.append(sr.date_queued.isoformat())
        row.append(sr.date_to_send.isoformat())
        row.append(sr.message.encode('utf-8'))
        writer.writerow(row)
        

def entry_output(writer):
    header = ['patient', 'published', 'item_type', 
	'entry_uid', 'feed', 'content', 'added', 'pct_max', 'pct_min']
    writer.writerow(header)
    seen = set()
    for es in EntrySeen.objects.all():
        row = []
        entry = es.entry
        seen.add(entry.id)
        row.append(es.patient.subject_number)
        row.append(entry.published.isoformat())
        row.append("EntrySeen")
        row.append(entry.uid)
        row.append(str(entry.feed))
        row.append(entry.content.encode('utf-8'))
        row.append(entry.added.isoformat())
        row.append(entry.percent_max)
        row.append(entry.percent_min)
        writer.writerow(row)
    unseen = Entry.objects.all().exclude(id__in=seen)
    for u in unseen:
        row = []
        entry = u
        row.append('')
        row.append(entry.published.isoformat())
        row.append("EntryUnseen")
        row.append(entry.uid)
        row.append(str(entry.feed))
        row.append(entry.content.encode('utf-8'))
        row.append(entry.added.isoformat())
        row.append(entry.percent_max)
        row.append(entry.percent_min)
        writer.writerow(row)

        

    

def wisepill_output(writer):
    props = [ 'patient', 'timestamp', 'item_type',
    	'message_type', 'msisdn', 'serialnumber', 'signalstrength', 'batterystrength', 'puffcount', 'ussdresponse', 'medicationcompartment', 'ce', ]

    #header
    writer.writerow(props)
    for wp in WisepillMessage.objects.all():
        row = []
        if wp.patient is None:
            row.append('')
        else:
            row.append(wp.patient.subject_number)
        row.append(wp.timestamp.isoformat())
        row.append('wisepill_message')
        row.append(wp.get_message_type_display())
        row.append(wp.msisdn)
        row.append(wp.serialnumber)
        row.append(wp.signalstrength)
        row.append(wp.batterystrength)
        row.append(wp.puffcount)
        row.append(wp.ussdresponse)
        row.append(wp.medicationcompartment)
        row.append(wp.ce)
        writer.writerow(row)

def csvwrite(filename, writefunc):
    with open(os.path.join('/home/aremind/outputs', filename), 'wb') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_MINIMAL)
        writefunc(writer)


def run():
    #per patient:
    #reminder times?
    #feeds

    #streams:
    
    #output pillsmissed
    csvwrite('pillsmissed.csv', pillsmissed_output)
    
    #output surveys
    csvwrite('patientsurvey.csv', surveys_output)

    #output all reminders
    #output sentnotification
    csvwrite('sentreminder.csv', reminder_output)
    #output patients per feed/vice versa
    #todo

    #output entry/seen
    csvwrite('entries.csv', entry_output)
    #output wisepill message
    csvwrite('wisepill.csv', wisepill_output)

