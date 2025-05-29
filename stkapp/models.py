from django.db import models

# Create your models here.
class Transaction(models.Model):
    # transaction id : field to store mpesa transaction id
    transaction_id = models.CharField(max_length=100, blank=True,null=True)
    # phone number : phone number initiating transaction
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(decimal_places=2, max_digits=10)
    # mpesa receipt number
    mpesa_receipt_number = models.CharField(max_length=100, blank=True,null=True)
    # transaction status : pending , processing , completed , failure
    status = models.CharField(max_length=100, blank=True,null=True)
    description = models.CharField(max_length=230,blank=True,null=True)
    transaction_date = models.DateTimeField(blank=True,null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(blank=True,null=True)
    name = models.CharField(max_length=100,blank=True,null=True)

    def __str__(self):
        #on object creation show this details
        print(f"Transaction ID: {self.mpesa_receipt_number} {self.name}")
        return f"Transaction ID: {self.mpesa_receipt_number} {self.name}"








