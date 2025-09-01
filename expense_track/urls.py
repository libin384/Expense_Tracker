from django.urls import path, include
from . import views

urlpatterns=[
    path('', views.home, name="home"),
    path('expenses',views.ExpenseListView.as_view(), name='expenses'),
    path('accounts/register/', views.register, name= 'register'),
    path('accounts/', include('django.contrib.auth.urls'))
]