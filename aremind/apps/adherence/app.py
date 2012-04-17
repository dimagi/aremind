#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
import datetime
import logging

from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from django.template import Context
from django.template.loader import get_template

from rapidsms.apps.base import AppBase
from rapidsms.messages import OutgoingMessage

from aremind.apps.adherence.models import Reminder, SendReminder, QuerySchedule
from aremind.apps.groups.models import Group
from aremind.apps.patients.models import Patient
from rapidsms.contrib.messagelog.models import Message

from email.mime.application import MIMEApplication

# In RapidSMS, message translation is done in OutgoingMessage, so no need
# to attempt the real translation here.  Use _ so that ./manage.py makemessages
# finds our text.
_ = lambda s: s


class AdherenceApp(AppBase):

    reminder = _('ARemind:')

    def start(self):
        self.info('started')

    def queue_outgoing_messages(self):
        """ generate queued messages for adherence reminders """
        reminders = Reminder.objects.ready()
        self.info('found {0} ready adherence reminder(s)'.format(reminders.count()))
        for reminder in reminders:
            # TODO: make sure this process is atomic
            count = reminder.queue_outgoing_messages()
            self.debug('queued {0} adherence reminder(s)'.format(count))
            reminder.set_next_date()

    def send_messages(self):
        """ send queued for delivery messages """

        messages = SendReminder.objects.filter(status='queued')[:20]
        self.info('found {0} reminder(s) to send'.format(messages.count()))
        for message in messages:
            connection = message.recipient.default_connection
            template = message.message
            if len(template) > 160:
                # Truncate at 160 characters but keeping whole words
                template = template[:160]
                words = template.split(' ')[:-1]
                template = u' '.join(words) + u'...'
            msg = OutgoingMessage(connection=connection, template=template)
            success = True
            try:
                self.router.outgoing(msg)
            except Exception, e:
                self.exception(e)
                success = False
            if success and msg.sent:
                self.debug('message sent successfully')
                message.status = 'sent'
                message.date_sent = datetime.datetime.now()
            else:
                self.debug('message failed to send')
                message.status = 'error'
            message.save()

    def cronjob(self):
        self.debug('cron job running')
        # grab all broadcasts ready to go out and queue their messages
        self.queue_outgoing_messages()
        # send queued messages
        self.send_messages()
        # Start any adherence queries
        for query_schedule in QuerySchedule.objects.filter(active=True):
            query_schedule.start_scheduled_queries()

"""
This method will send the csv report to all members of the 
"Daily Report Recipients" group.
"""
def send_fhi_report_email():
    # Retrieve all recipients of the report from the Group with name DEFAULT_DAILY_REPORT_GROUP_NAME
    recipients = []
    for contact in Group.objects.get(name = settings.DEFAULT_DAILY_REPORT_GROUP_NAME).contacts.all():
        recipients.append(contact.email)
    
    # If there is at least one recipient, send the email
    if len(recipients) > 0:
        # Construct the email message
        email = EmailMessage (
            subject = "FHI Daily Report"
           ,body = "You are receiving this automated email because you are signed up to receive the FHI Daily Report. Please find the results attached in csv format."
           ,to = recipients
        )
        
        # Construct the attachment
        template = get_template("adherence/fhi_report.csv")
        context = {}
        context["patients"] = Patient.objects.all().order_by("date_enrolled")
        context["messages"] = Message.objects.all().order_by("date")
        csv_data = template.render(Context(context))
        report = MIMEApplication(csv_data, "csv")
        report.add_header("content-disposition", "attachment", filename="report.csv")
        email.attach(report)
        
        # Send the email
        email.send()
