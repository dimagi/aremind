from django.db import models


class ContactPin(models.Model):
    pin = models.CharField(max_length=20, blank=True, help_text='A PIN code '
                           'for SMS authentication workflows.')

    """
    UW Kenya Implementation
    
    Added password field to Contact model for authentication in decisiontree surveys.
    Also added mobile network to Contact model.
    """
    password = models.CharField(max_length=20, blank=False, help_text="The password used for SMS survey authentication.")
    mobile_network = models.CharField(max_length=50, blank=True)

    class Meta:
        abstract = True
