import datetime
import re

from django.db.models import Q

from rapidsms.apps.base import AppBase
from rapidsms.contrib.scheduler.models import EventSchedule
from rapidsms.messages.outgoing import OutgoingMessage

from afrims.apps.reminders import models as reminders

# In RapidSMS, message translation is done in OutgoingMessage, so no need
# to attempt the real translation here.  Use _ so that ./manage.py makemessages
# finds our text.
_ = lambda s: s


def scheduler_callback(router):
    """
    Basic rapidsms.contrib.scheduler.models.EventSchedule callback
    function that runs RemindersApp.cronjob()
    """
    app = router.get_app("afrims.apps.reminders")
    app.cronjob()


class RemindersApp(AppBase):
    """ RapidSMS app to send appointment reminders """

    # for production, we'll probably want something like:
#    cron_schedule = {'minutes': ['0'], 'hours': ['10']}
    # for testing and debugging, run every minute:
    cron_schedule = {'minutes': '*'}
    cron_name = 'reminders-cron-job'
    cron_callback = 'afrims.apps.reminders.app.scheduler_callback'

    pin_regex = re.compile(r'^\d{4,6}$')
    conf_keyword = '1'
    
    future_appt_msg = _('Hello, {name}. You have an upcoming appointment in '
                        '{days} days, on {date}. Please reply with '
                        '{confirm_response} to confirm.')
    near_appt_msg = _('Hello, {name}. You have an appointment {day}, {date}. '
                       'Please reply with {confirm_response} to confirm.')
    not_registered = _('Sorry, your mobile number is not registered.')
    no_reminders = _('Sorry, I could not find any reminders awaiting '
                     'confirmation.')
    incorrect_pin = _('That is not your PIN code. Please reply with the '
                      'correct PIN code.')
    pin_required = _('Please confirm appointments by sending your PIN code.')
    thank_you = _('Thank you for confirming your upcoming appointment.')

    def start(self):
        """ setup event schedule to run cron job """
        try:
            schedule = EventSchedule.objects.get(description=self.name)
        except EventSchedule.DoesNotExist:
            schedule = EventSchedule.objects.create(description=self.name,
                                                    callback=self.cron_callback,
                                                    **self.cron_schedule)
        schedule.callback = self.cron_callback
        for key, val in self.cron_schedule.iteritems():
            if hasattr(schedule, key):
                setattr(schedule, key, val)
        schedule.save()
        self.info('started')

    def handle(self, msg):
        """
        Handles messages that start with a '1' (to ease responding in
        alternate character sets).
        
        Updates the SentNotification status to 'confirmed' for the given user
        and replies with a thank you message.
        """
        msg_parts = msg.text.split()
        if not msg_parts:
            return False
        response = msg_parts[0]
        if response != self.conf_keyword and not self.pin_regex.match(response):
            return False
        contact = msg.connection.contact
        if not contact:
            msg.respond(self.not_registered)
            return True
        if contact.pin and response == self.conf_keyword:
            msg.respond(self.pin_required)
            return True
        if contact.pin and response != contact.pin:
            msg.respond(self.incorrect_pin)
            return True
        notifs = reminders.SentNotification.objects.filter(recipient=contact,
                                                           status='sent')
        if not notifs.exists():
            msg.respond(self.no_reminders)
            return True
        sent_notification = notifs.order_by('-date_sent')[0]
        sent_notification.status = 'confirmed'
        sent_notification.date_confirmed = datetime.datetime.now()
        sent_notification.save()
        msg.respond(self.thank_you)

    def queue_outgoing_notifications(self):
        """ generate queued appointment reminders """
        # TODO: make sure this task is atomic
        today = datetime.date.today()
        for notification in reminders.Notification.objects.all():
            self.info('Scheduling notifications for %s' % notification)
            days_delta = datetime.timedelta(days=notification.num_days)
            appt_date = today + days_delta
            patients = reminders.Patient.objects.filter(next_visit=appt_date,
                                                        contact__isnull=False,)
            already_sent = Q(contact__sent_notifications__appt_date=appt_date) &\
                           Q(contact__sent_notifications__notification=notification)
            confirmed = Q(contact__sent_notifications__appt_date=appt_date) &\
                        Q(contact__sent_notifications__status='confirmed')
            # .exclude() generates erroneous results - use filter(~...) instead
            patients = patients.filter(~already_sent)
            if notification.recipients == 'confirmed':
                patients = patients.filter(confirmed)
            elif notification.recipients == 'unconfirmed':
                # unconfirmed should include those to whom we haven't sent
                # any reminders yet, so just exclude the confirmed ones
                patients = patients.filter(~confirmed)
            self.info('Queuing reminders for %s patients.' % patients.count())
            for patient in patients:
                self.debug('Creating notification for %s' % patient)
                if patient.contact.pin:
                    confirm_response = 'your PIN'
                else:
                    confirm_response = self.conf_keyword
                msg_data = {
                    'days': notification.num_days,
                    'date': appt_date.strftime('%B %d, %Y'),
                    'name': patient.contact.name,
                    'confirm_response': confirm_response,
                }
                if notification.num_days == 0:
                    msg_data['day'] = 'today'
                    message = self.near_appt_msg.format(**msg_data)
                elif notification.num_days == 1:
                    msg_data['day'] = 'tomorrow'
                    message = self.near_appt_msg.format(**msg_data)
                else:
                    message = self.future_appt_msg.format(**msg_data)
                date_to_send = datetime.datetime.combine(today, patient.reminder_time or notification.time_of_day)
                notification.sent_notifications.create(
                                        recipient=patient.contact,
                                        appt_date=appt_date,
                                        date_queued=datetime.datetime.now(),
                                        date_to_send=date_to_send,
                                        message=message)

    def send_notifications(self):
        """ send queued for delivery messages """
        notifications = reminders.SentNotification.objects.filter(
                                    status='queued',
                                    date_to_send__lt=datetime.datetime.now())
        count = notifications.count()
        self.info('found {0} notification(s) to send'.format(count))
        for notification in notifications:
            connection = notification.recipient.default_connection
            if not connection:
                self.debug('no connection found for recipient {0}, unable '
                           'to send'.format(notification.recipient))
                continue
            msg = OutgoingMessage(connection=connection,
                                  template=notification.message)
            success = True
            try:
                msg.send()
            except Exception, e:
                self.exception(e)
                success = False
            if success:
                self.debug('notification sent successfully')
                notification.status = 'sent'
                notification.date_sent = datetime.datetime.now()
            else:
                self.debug('notification failed to send')
                notification.status = 'error'
            notification.save()

    def cronjob(self):
        self.debug('{0} running'.format(self.cron_name))
        # grab all reminders ready to go out and queue their messages
        self.queue_outgoing_notifications()
        # send queued notifications
        self.send_notifications()