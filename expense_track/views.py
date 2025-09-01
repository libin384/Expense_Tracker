from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from expense_track import models
from .models import Expense, Account
from .forms import ExpenseForm
from django.views.generic import TemplateView, ListView
from django.views.generic.edit import FormView
from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.db.models import Sum, Count, F
import plotly.express as px
from collections import defaultdict
from plotly.graph_objs import *
from django.utils.safestring import mark_safe
import json
import pandas as pd

# Create your views here.


def home(request):
    return render(request, 'home/home.html')

grouped_expenses = defaultdict(list)
graph_data = {}

def expenses_view(request):
    expenses = Expense.objects.all().order_by("date")

    # Group by month-year
    for expense in expenses:
        month = expense.date.strftime("%B %Y")  # Example: "August 2025"
        grouped_expenses[month].append(expense)

    context = {
        "grouped_expenses": dict(grouped_expenses),
        "form": ExpenseForm(),   # if you’re using a form
        "graph_data": {"data": [], "layout": {}}  # if you’re using plotly
    }
    return render(request, "expenses_list.html", context)


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('expenses')
    else:
        form = UserCreationForm()
    return render(request, "expenses_list.html", {"form": form, "grouped_expenses": grouped_expenses, "graph_data": graph_data})


def generate_graph(data):
    df = pd.DataFrame(data)

    df['month'] = pd.to_datetime(df['month'], format="%Y-%m")
    df = df.sort_values(by='month')

    # Plot
    fig = px.bar(df, x='month', y='expenses', title='Monthly Expenses')

    # Format ticks as "Aug 2025"
    fig.update_xaxes(tickformat="%b %Y")

    fig.update_layout(
        xaxis=dict(rangeslider=dict(visible=True)),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='rgba(0,0,0,1)'
    )
    fig.update_traces(marker_color='#008c41')

    return fig.to_json()

class ExpenseListView(FormView):
    template_name = 'expense_track/expenses_list.html'
    form_class = ExpenseForm
    success_url = '/expenses'

    def form_valid(self, form):
        account, _ = Account.objects.get_or_create(
            user=self.request.user,
            defaults={'name': f"{self.request.user.username}'s Account", 'expense': 0}
        )

        expense = Expense(
            name=form.cleaned_data['name'],
            amount=form.cleaned_data['amount'],
            interest_rate=form.cleaned_data['interest_rate'],
            date=form.cleaned_data['date'],
            end_date=form.cleaned_data['end_date'],
            long_term=form.cleaned_data['long_term'],
            user=self.request.user
        )
        expense.save()
        account.expense_list.add(expense)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        accounts = Account.objects.filter(user=user)

        expense_data_graph = {}
        all_expenses = []

        for account in accounts:
            expenses = account.expense_list.all()
            all_expenses.extend(expenses)
            for expense in expenses:
                if expense.long_term and expense.monthly_expense:
                    current_date = expense.date
                    while current_date <= expense.end_date:
                        year_month = current_date.strftime('%Y-%m')
                        expense_data_graph.setdefault(year_month, []).append({
                            'name': expense.name,
                            'amount': expense.monthly_expense,
                            'date': expense.date,
                            'end_date': expense.end_date,
                        })
                        current_date += relativedelta(months=1)
                else:
                    year_month = expense.date.strftime('%Y-%m')
                    expense_data_graph.setdefault(year_month, []).append({
                        'name': expense.name,
                        'amount': expense.amount,
                        'date': expense.date
                    })

        # Aggregate by month
        aggregated_data = [
            {'year_month': key, 'expense': sum(item['amount'] for item in value)}
            for key, value in expense_data_graph.items()
        ]

        # Prepare graph data
        graph_data = {
            'month': [item['year_month'] for item in aggregated_data],
            'expenses': [item['expense'] for item in aggregated_data]
        }
        graph_data['chart'] = generate_graph(graph_data)

        context['aggregated_data'] = aggregated_data
        context['graph_data'] = mark_safe(graph_data['chart'])
        context['expenses'] = all_expenses
        context['expense_data'] = expense_data_graph

        return context



