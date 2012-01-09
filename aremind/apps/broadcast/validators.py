from django.core.exceptions import ValidationError

from aremind.apps.reminders.app import RemindersApp


def validate_keyword(value):
    if value == RemindersApp.conf_keyword:
        msg = u"'%s' is a keyword reserved for the appointment reminders." %  RemindersApp.conf_keyword
        raise ValidationError(msg)

validate_keyword.help_text = u"""
Messages will be forwarded based on matching the start of the message to the given keyword.
There are a few keywords which you must avoid because of conflicts with other applications:
'%(conf)s' is currently used by the appointment reminders application.""" % {
    'conf': RemindersApp.conf_keyword,
}
