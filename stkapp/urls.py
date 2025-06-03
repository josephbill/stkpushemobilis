from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'), # front page
    #path to prompt stk push
    path('stk_push/', views.stk_push, name='stk_push'),
    # the routes for status checking
    path('waiting/<int:transaction_id>/', views.waiting_page, name="waiting_page"),
   # this is the route that will receive the status of our transaction
    path('callback/', views.callback, name="callback"),
    # this route confirms the status from above callback result
    path('check-status/<int:transaction_id>/', views.check_status, name="check-status"),
    # payments views (successful, failed or cancelled)
    path('payment-success/', views.payment_success, name="payment-success"),
    path('payment-failed/', views.payment_failed, name="payment-failed"),
    path('payment-cancelled/', views.payment_cancelled, name="payment-cancelled"),
]